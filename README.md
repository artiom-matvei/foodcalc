# foodcalc

Application is deployed at https://nutrient-calculator.herokuapp.com/ (taken down because of a bug that was found, only one user eaten food is shown because it was hard coded in template variable in eaten_food() function in app.py. Change user_id=2 to user_id=user_id and I think it should work.)

1. To use it, create an account by registering. 
2. Login with the credentials. 
3. Go to "View or change your daily recommended intake of nutrients".
4. In the "All foods" page, add eaten foods by clicking FoodID number and adding the number of grams. This will be seen in "Eaten food" view.
5. This will be used to calculate the percentage of recomended nutrient intake in the "View eaten food" page.
6. To delete eaten food
