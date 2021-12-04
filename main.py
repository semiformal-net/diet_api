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

solvers.options['show_progress'] = False
solvers.options['glpk'] = {'msg_lev' : 'GLP_MSG_OFF'} #mute all output from glpk

def find_diet(nfoods=6,exclude_food_ids=[], metric_nutrients=[208],metric_weights=[1]):

    N_FOODS=nfoods
    exclude_food_ids=exclude_food_ids
    metric_nutrients=metric_nutrients
    metric_weights=metric_weights

    #
    # Internal constants
    #
    Nseed=500
    #
    # Load nutrient data
    #
    (nutrients,reqd,limt,food_desc,nutrient_desc)=load_data()
    print( '[*] Loaded %d foods from database' % nutrients.shape[0] )
    NT_DIM=nutrients.shape[0]
    
    #
    # drop any foods that we passed in exclude list
    #
    if len(exclude_food_ids)>0:
        valid_drop=list(set(nutrients.index) & set(exclude)) # the food ids that are passed and are in the index
        if len(valid_drop)>0:
            nutrients.drop(index=valid_drop,inplace=True)
    
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
        print('error')

    if cluster_food_count != nutrients.shape[0] :
        print('error')
        
    Nclust=clust.max()+1
    
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
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=NT_DIM, indpb=0.1)
    #toolbox.register("select", tools.selBest, k=3)
    toolbox.register("select", tools.selTournament, tournsize=10)
    toolbox.register("evaluate", evaluate, nut=nutrients,limt=limt,reqd=reqd,metric_nutrients=metric_nutrients,metric_weights=metric_weights)

    # used to make a seed population (only) ; per: https://deap.readthedocs.io/en/master/tutorials/basic/part1.html?highlight=seeding#seeding-a-population
    toolbox.register("population_guess", InitPopulation, list, creator.Individual, N_FOODS,Nclust,Nseed,clust )

    stats = tools.Statistics(key=lambda ind: ind.fitness.values)
    stats.register("min", numpy.min)
    stats.register("median", numpy.median)
    stats.register("max", numpy.max)
    
    #pop = toolbox.population(n=300) # totally random initial population
    pop = toolbox.population_guess()
    pop, logbook = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=10,stats=stats, verbose=True) # verbose=False for prod
    
    # clean up
    pool.close()

    best=tools.selBest(pop, k=1)
    best=best[0]    

    # final (sort of redundant LP fit on best diet 
    evaluate(best, nut=nutrients,limt=limt,reqd=reqd)
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

    nutrient_full.columns=nutrient_desc.loc[nutrient_full.columns,'name']
    nutrient_full['Description']=food_desc.loc[nutrient_full.index,:].values
    nutrient_full=nutrient_full.set_index(['Description']).transpose()

    nutrient_full['Total']=nutrient_full.sum(axis=1,numeric_only=True)
    nutrient_full.to_dict()

    out={}
    out['raw_amount']=raw_amount
    out['scaled_amount']=scaled_amount
    out['food_description']=food_description
    out['nutrient_full']=nutrient_full.to_dict()
    return out

def main():
    with open('query.json') as f:
        queries=json.load(f)
    output=[]
    for query in queries:
        result=find_diet(nfoods=query['nfoods'],exclude_food_ids=query['exclude_food_ids'], metric_nutrients=query['metric_nutrients'],metric_weights=query['metric_weights'])
        print(result)
        output.append(result)

    with open('/workspace/output.json', 'w') as f:
        json.dump(output, f)
        f.write(linesep)

if __name__ == "__main__":
    main()
