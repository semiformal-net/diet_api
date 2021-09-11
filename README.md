# Diet API

This is a dockerized rest API to compute nutritionally optimal diets

# Inputs

It expects POST data containing

```
{
 "nfoods":6,
 "exclude_food_ids":[],
 "metric_nutrients":[208],
 "metric_weights":[1]
}
```

- nfoods: The maximum number of foods the solution diet can contain
- exclude_food_ids: foods to be excluded from all diets (by USDA food id)
- metric_nutrients: the nutrients to consider in optimization. by USDA nutrient ID (208 = calories)
- metric_weights: the multiplier for each `metric_nutrients`. The optimization (minimization) target is the weighted sum of all metric nutrients in the diet. For example setting `metric_nutrients=[208]` and `metric_weights=[1]` will minimize the total calories in the diet. Setting `metric_weights=[-1]` will maximize calories.

# Outputs

The amount of each food in the diet (some values may be zero). For example,

```
{
 "food_amounts":[1.48297,0.07821,3.52415,0.12568,5.43694,7.93208],
 "food_ids":[17428,16124,43019,17195,11965,11281]
}
```

# Environment

Docker container with `gunicorn` running a flask app.

## Testing locally

Build the container:

```
docker build --tag find_diet:python .
docker run --rm -p 8080:8080 -e PORT=8080 find_diet:python
```

Hit the API with curl:

```
curl -i -H "Content-Type: application/json" -X POST -d @/tmp/json.txt http://localhost:8080/find_diet
```

Where `/tmp/json.txt` contains the inputs,

```
{
 "nfoods":6,
 "exclude_food_ids":[],
 "metric_nutrients":[208],
 "metric_weights":[1]
}
```