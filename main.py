import sys
from libraries import *
from flask import Flask, request, jsonify
from os import path
import pickle
import pandas
import numpy
from deap import base, creator, tools, algorithms
from cvxopt import matrix, solvers # an alternative linear programming library
import random
from time import time
import multiprocessing

solvers.options['show_progress'] = False
solvers.options['glpk'] = {'msg_lev' : 'GLP_MSG_OFF'} #mute all output from glpk


app = Flask(__name__)

@app.route('/foo', methods=['POST']) 
def foo():
    data = request.json
    return jsonify(data)

@app.route('/find_diet', methods=['POST']) 
def find_diet():

    data = request.json
    N_FOODS=data['nfoods']
    exclude_food_ids=data['exclude_food_ids']
    metric_nutrients=data['metric_nutrients']
    metric_weights=data['metric_weights']

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
    if path.exists('/clust.pkl'):
        clust=pickle.load( open( "/clust.pkl", "rb" ) )
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
    pop, logbook = algorithms.eaSimple(pop, toolbox, cxpb=0.5, mutpb=0.2, ngen=50,stats=stats, verbose=True)
    
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
    
    return(jsonify({ 'food_ids':food_ids, 'food_amounts':food_amounts }))

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
