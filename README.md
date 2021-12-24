# Diet API

This is a dockerized rest API to compute nutritionally optimal diets. This version abuses cloud build to do all the computation in batch.

# Inputs

It expects `query.json` data containing a list (!) of diet queries, for example,

```
[{
 "nfoods":6,
 "exclude_food_ids":[],
 "include_food_ids":[5009,5140,5147,5166,5308,5315,5622,5642,9003,9004,9021,9037,9038,9039,9040,9042,9050,9057,9060,9063,9070,9077,9078,9083,9084,9087,9089,9107,9111,9112,9113,9114,9116,9117,9118,9129,9131,9132,9139,9140,9144,9146,9148,9149,9150,9156,9159,9164,9167,9176,9181,9183,9184,9190,9191,9193,9200,9201,9202,9203,9205,9216,9218,9226,9231,9236,9252,9263,9265,9266,9277,9279,9286,9287,9302,9307,9316,9322,9326,9340,9412,9413,9414,9415,9422,9429,9430,9433,9445,9449,9500,9501,9502,9503,9504,10007,10021,11001,11007,11011,11026,11029,11031,11043,11046,11048,11050,11052,11080,11086,11088,11090,11096,11098,11109,11112,11114,11116,11119,11124,11135,11143,11147,11156,11161,11165,11167,11191,11197,11201,11203,11205,11207,11209,11211,11213,11215,11216,11218,11220,11226,11233,11238,11239,11240,11246,11248,11250,11251,11252,11253,11257,11260,11265,11266,11270,11278,11282,11291,11292,11293,11294,11297,11298,11300,11304,11333,11344,11352,11353,11354,11355,11422,11427,11429,11430,11435,11450,11452,11457,11467,11475,11477,11482,11485,11489,11492,11495,11507,11518,11527,11529,11564,11568,11588,11591,11593,11595,11597,11599,11601,11622,11637,11641,11643,11653,11670,11676,11677,11695,11696,11722,11739,11741,11749,11750,11819,11821,11900,11950,11951,11952,11953,11954,11957,11959,11960,11965,11972,11973,11974,11976,11977,11979,11981,11987,11990,11993,11995,12001,12004,12024,12037,12039,12058,12061,12063,12087,12093,12097,12098,12104,12120,12127,12131,12142,12151,12155,12158,12163,12202,12205,12220,13020,14411,14412,14429,15009,15012,15016,15029,15034,15037,15040,15047,15052,15063,15067,15082,15086,15100,15111,15116,15118,15137,15140,15148,15165,15169,15178,15188,15191,15192,15196,15197,15200,15202,15203,15204,15205,15209,15210,15211,15212,15216,15217,15218,15220,15221,15222,15226,15227,15230,15231,15233,15235,15237,15239,15241,15244,15246,15247,15262,15267,15269,15271,15273,16390,17000,17224,19296,19911,19912,20001,20005,20008,20031,20033,20035,20036,20038,20040,20044,20050,20052,20054,20062,20067,20069,20071,20072,20073,20074,20075,20076,20087,20088,20138,20140,20142,20314,20444,20450,20452,20466,43282,43283,43392],
 "targets": {},
 "minima": {"208": 1900,
        "205": 250,
        "203": 85,
        "204": 65
},

 "maxima":{"208": 2100}
}]

```

- nfoods: The maximum number of foods the solution diet can contain
- exclude_food_ids: foods to be excluded from all diets (by USDA food id)
- include_food_ids: foods to be included from all diets (by USDA food id)
- targets: a precise target for a given nutrient (deprecated)
- minima: minimum values for nutrients
- maxima: maximum values for nutrients

# Outputs

The amount of each food in the diet (some values may be zero). This is a list of outputs corresponding the the list of inputs above. For example,

```
[{
 "food_amounts":[1.48297,0.07821,3.52415,0.12568,5.43694,7.93208],
 "food_ids":[17428,16124,43019,17195,11965,11281]
}]
```

# Environment

Docker container with `main.py` entrypoint. The container should run once, finish its work, then terminate.

## Testing locally

Note that the container expects a `/workspace` directory. Google cloud build will make this automatically, but if running locally you need to mount it.

```
docker build --tag find_diet:batch .
mkdir /tmp/workspace/
docker run -v /tmp/workspace/:/workspace find_diet:batch
```

The container will grind all available CPUs on your machine then output `/tmp/workspace/output.json`

## Deploy with Google cloud run

```
PROJECT_ID=diets-325702

gcloud config set project $PROJECT_ID

#make a bucket
gsutil mb gs://dietbatch

# build gcr.io/diets-325702/diet_api:batch
#  this container contains a query.json file with diet jobs to run
#  the container outputs the results to /workspace/output.json (hardcoded)

gcloud builds submit --config cloudbuild.yaml

# this "build" runs the above container
# the container outputs the results to /workspace/output.json (hardcoded)
#  (cloud build mounts /workspace for all jobs by default)
# the build job uploads the output.json to gs://dietbatch
gcloud builds submit --config cloudbuild_batch.yaml
```
