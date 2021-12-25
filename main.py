import sys
from libraries import *
from os import path,linesep
import pickle
import pandas
import numpy
from deap import base, creator, tools, algorithms
from cvxopt import matrix, solvers # an alternative linear programming library
import random
from time import time
import multiprocessing
import json
import datetime

solvers.options['show_progress'] = False
solvers.options['glpk'] = {'msg_lev' : 'GLP_MSG_OFF'} #mute all output from glpk

def find_diet(nfoods=6,exclude_food_ids=[],include_food_ids=[], targets={208: 2000},minima={},maxima={}):

    N_FOODS=nfoods
    exclude_food_ids=exclude_food_ids
    include_food_ids=include_food_ids
    targets=targets

    #
    # Internal constants
    #
    Nseed=500
    #
    # Load nutrient data
    #
    (nutrients,reqd,limt,food_desc,nutrient_desc,weights_minmax)=load_data()
    print( '[*] Loaded %d foods from database' % nutrients.shape[0] )
    
    if len(minima)>0:
        reqd=pandas.Series(minima).combine_first(reqd)
    if len(maxima)>0:
        limt=pandas.Series(maxima).combine_first(limt)
    
    #
    # Load food clusters
    #
    cluster_food_count=0
    if path.exists('./clust.pkl'):
        clust=pickle.load( open( "./clust.pkl", "rb" ) )
        print( '[*] Found pickle file with %d clusters and %d foods' % (clust.max()+1,len(clust)) )
        Nclust=clust.max()+1
        cluster_food_count=len(clust)
    else:
        print('[!] Clustering error: 1')

    if cluster_food_count != nutrients.shape[0] :
        print('[!] Clustering error: 2')
        
    Nclust=clust.max()+1
    cluster_series=pandas.Series(clust, index=nutrients.index)
    
    #
    # Include and exclude foods.
    #  the logic is that:
    #   if include_food_ids: include foods in include_food_ids - exclude_food_ids
    #   else: include foods in default_food_ids - exclude_food_ids
    #
    if len(include_food_ids)>0 or len(exclude_food_ids)>0:
        drop1=list(set(nutrients.index).symmetric_difference(set(include_food_ids))) # drop items that are in database, but are not in include list
        if len(drop1)>0:
            nutrients.drop(index=drop1,inplace=True)
        drop2=list(set(nutrients.index).intersection(set(exclude_food_ids))) # drop items that are available which are also in the exclude list
        if len(drop2)>0:
            nutrients.drop(index=drop2,inplace=True)

    #reset clusters after dropping some foods
    #clust=cluster_series[nutrients.index].values
    (clust, factors)=pandas.factorize(cluster_series[nutrients.index[0:100]])
    Nclust=len(factors)
    
    # shape
    NT_DIM=nutrients.shape[0]
    
    print('[*] Working with %d valid foods' % (nutrients.shape[0]) )
    
    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin) # an individual comprises a list (of food IDs)

    toolbox = base.Toolbox()
    pool = multiprocessing.Pool()
    toolbox.register("map", pool.map)
    # Attribute generator 
    toolbox.register("attr_foodid", random.randrange, NT_DIM)
    # Structure initializers
    toolbox.register("individual", tools.initRepeat, creator.Individual, 
        toolbox.attr_foodid, N_FOODS)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=(NT_DIM-1), indpb=0.1)
    #toolbox.register("select", tools.selBest, k=3)
    toolbox.register("select", tools.selTournament, tournsize=10)
    toolbox.register("evaluate", evaluate, nut=nutrients,limt=limt,reqd=reqd,weights_minmax=weights_minmax,targets=targets)

    # used to make a seed population (only) ; per: https://deap.readthedocs.io/en/master/tutorials/basic/part1.html?highlight=seeding#seeding-a-population
    toolbox.register("population_guess", InitPopulation, list, creator.Individual, N_FOODS,Nclust,Nseed,clust )
    
    hof = tools.HallOfFame(500)

    stats = tools.Statistics(key=lambda ind: ind.fitness.values)
    stats.register("min", numpy.min)
    stats.register("median", numpy.median)
    stats.register("max", numpy.max)
    
    pop = toolbox.population(n=300) # totally random initial population
    #pop = toolbox.population_guess()
    pop, logbook = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=50,stats=stats, verbose=True,halloffame=hof) # verbose=False for prod
    
    # clean up
    pool.close()

    best=tools.selBest(pop, k=1)
    best=best[0]    
    
    print( 'best', best )

    # final (sort of redundant LP fit on best diet 
    #evaluate(best, nut=nutrients,limt=limt,reqd=reqd)
    nt=nutrients.iloc[best,:]
    c = matrix(numpy.repeat(1.0,nt.shape[0]))
    np_G= numpy.concatenate(
                            (   nt.transpose().values, 
                                nt.transpose().multiply(-1.0).values,
                                numpy.diag(numpy.repeat(-1,nt.shape[0])) 
                            )
                        ).astype(numpy.double) 
    G = matrix( np_G ) 
    h = matrix( numpy.concatenate( (
                    limt.values, 
                    reqd.multiply(-1.0).values, 
                    numpy.repeat(0.0,nt.shape[0])
                ) ).astype(numpy.double) )    
    o = solvers.lp(c, G, h, solver='glpk')
    food_amounts=numpy.array(o['x'])[:,0]
    food_amounts=list(numpy.round(abs(food_amounts),5))
    food_ids=list(nt.index)

    ids=[]
    amt=[]
    raw_amount={}
    scaled_amount={}
    food_description={}
    for i,v in enumerate(food_ids):
        if food_amounts[i] > 0:
            raw_amount[v]=food_amounts[i]
            scaled_amount[v]=food_amounts[i]*100
            food_description[v]=food_desc.loc[v,:].values[0]
            ids.append(v)
            amt.append(food_amounts[i])

    nutrient_full=nutrients.loc[ ids  ,:].copy()
    nutrient_full=nutrient_full.apply( lambda x: x * numpy.array(amt) , axis=0 ) # multiply by food amounts
    nutrient_full=nutrient_full.join( food_desc )
    nutrient_full=nutrient_full.rename(columns={'long_desc':'Description'})
    nutrient_full=nutrient_full.set_index(['Description']).transpose()
    nutrient_full=nutrient_full.join(nutrient_desc).set_index('name')
    nutrient_full['Total']=nutrient_full.sum(axis=1,numeric_only=True)
    
    out={}
    out['id']='%x' % random.getrandbits(64)
    out['time_utc']=str(datetime.datetime.utcnow())
    out['raw_amount']=raw_amount
    out['scaled_amount']=scaled_amount
    out['food_description']=food_description
    out['nutrient_full']=nutrient_full.to_dict()
    out['halloffame']=[ {'candidate':i,'score':i.fitness.values[0]} for i in hof[0:51] ]
    return out

def report(json):
    nutrient_full_html=pandas.DataFrame.from_dict(json['nutrient_full']).style.format(precision=1).to_html()
    amt=pandas.DataFrame( pandas.Series( json['scaled_amount'] ),columns=['amount (g)'] )
    nm=pandas.DataFrame( pandas.Series( json['food_description'] ),columns=['name'] )
    diet_html=nm.join(amt).style.format(precision=1).to_html()
    header='''
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    * {
      box-sizing: border-box;
    }

    .row {
      margin-left:-5px;
      margin-right:-5px;
    }

    .column {
      float: left;
      width: 50%;
      padding: 5px;
    }

    /* Clearfix (clear floats) */
    .row::after {
      content: "";
      clear: both;
      display: table;
    }
    
    table {
      border-collapse: collapse;
      border-spacing: 0;
      width: 100%;
      border: 1px solid #ddd;
    }

    th, td {
      text-align: left;
      padding: 16px;
      border: 1px solid grey;
      text-align: center;
    }

    tr:nth-child(even) {
      background-color: #f2f2f2;
    }
    </style>
    </head>
    <body>
    '''
    title='<h2>Diet report</h2><p>ID: {}</p><p>Time: {}</p>'.format( json['id'],json['time_utc'] )
    
    full_json_data='<a href="data:application/json;charset=UTF-8,{}" download="raw_diet_output.json">raw json</a>'.format( json )
    
    tables='<div class="row"><div class="column">' + diet_html +'</div><div class="column">'+ nutrient_full_html + '</div></div>'
    
    footer='''
    </body>
    </html>
    '''
    with open('/workspace/report.html','w') as f:
        f.write( header+title+full_json_data+tables+footer )
    

def main():
    with open('query.json') as f:
        queries=json.load(f)
    output=[]
    for query in queries:
        
        query['targets'] = {int(k):int(v) for k,v in query['targets'].items()} # json has to have dict keys as string. we expect them as int. convert.
        query['minima'] = {int(k):int(v) for k,v in query['minima'].items()} # json has to have dict keys as string. we expect them as int. convert.
        query['maxima'] = {int(k):int(v) for k,v in query['maxima'].items()} # json has to have dict keys as string. we expect them as int. convert.
        out=find_diet(nfoods=query['nfoods'],exclude_food_ids=query['exclude_food_ids'],include_food_ids=query['include_food_ids'], 
                      targets=query['targets'],minima=query['minima'],maxima=query['maxima'])
        print(out)
        output.append(out)

    with open('/workspace/output.json', 'w') as f:
        json.dump(output, f)
        f.write(linesep)

if __name__ == "__main__":
    main()
