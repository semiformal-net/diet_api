# Diet API

This is a dockerized rest API to compute nutritionally optimal diets. This version abuses cloud build to do all the computation in batch.

# Inputs

It expects `query.json` data containing a list (!) of diet queries

```
[{
 "nfoods":6,
 "exclude_food_ids":[],
 "metric_nutrients":[208],
 "metric_weights":[1]
}]
```

- nfoods: The maximum number of foods the solution diet can contain
- exclude_food_ids: foods to be excluded from all diets (by USDA food id)
- metric_nutrients: the nutrients to consider in optimization. by USDA nutrient ID (208 = calories)
- metric_weights: the multiplier for each `metric_nutrients`. The optimization (minimization) target is the weighted sum of all metric nutrients in the diet. For example setting `metric_nutrients=[208]` and `metric_weights=[1]` will minimize the total calories in the diet. Setting `metric_weights=[-1]` will maximize calories.

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
