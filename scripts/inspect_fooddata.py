import pandas as pd

base = r'C:\Users\Lenovo\Downloads\smartclub_analytics\FoodData_Central_foundation_food_csv_2025-12-18'

food = pd.read_csv(f'{base}/food.csv')
nutrient = pd.read_csv(f'{base}/nutrient.csv')
food_nutrient = pd.read_csv(f'{base}/food_nutrient.csv')

print('=== food ===')
print('cols:', food.columns.tolist())
print('shape:', food.shape)
print(food.head(3).to_string())
print()
print('=== nutrient ===')
print('cols:', nutrient.columns.tolist())
print(nutrient.head(10)[['id','name','unit_name']].to_string())
print()
print('=== food_nutrient ===')
print('cols:', food_nutrient.columns.tolist())
print(food_nutrient.shape)
print(food_nutrient.head(5).to_string())
