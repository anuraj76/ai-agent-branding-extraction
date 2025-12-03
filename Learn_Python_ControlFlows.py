'''
# Sal's Shipping Calculator

## Problem Description
Sal runs the biggest shipping company in the tri-county area, Sal's Shippers. 
This program calculates the cheapest shipping method based on package weight.

## Shipping Options

### Ground Shipping
| Weight Range | Price per Pound | Flat Charge |
|--------------|----------------|-------------|
| ≤ 2 lb       | $1.50          | $20.00      |
| 2-6 lb       | $3.00          | $20.00      |
| 6-10 lb      | $4.00          | $20.00      |
| > 10 lb      | $4.75          | $20.00      |

### Ground Shipping Premium
- Flat charge: $125.00 (no weight-based fees)

### Drone Shipping
| Weight Range | Price per Pound | Flat Charge |
|--------------|----------------|-------------|
| ≤ 2 lb       | $4.50          | $0.00       |
| 2-6 lb       | $9.00          | $0.00       |
| 6-10 lb      | $12.00         | $0.00       |
| > 10 lb      | $14.25         | $0.00       |

'''
#Lets define a weight variable (in lbs)
#weight = 8.4
#weight = 1.5
#weight = 4.8
weight = 41.5
#Ground Shipping where weight is in lbs and charges in $ 
flat_charge = 20
if weight <= 2:
  shipping_price = weight * 1.50 + flat_charge
  print('shipping_price:', shipping_price)
elif weight <= 6:
  shipping_price = weight * 3.00 + flat_charge
  print('shipping_price:', shipping_price)
elif weight <= 10:
  shipping_price = weight * 4.00 + flat_charge
  print('shipping_price:', shipping_price)
else:
  shipping_price = weight * 4.75 + flat_charge
  print('shipping_price:', shipping_price) 

#Cost of shipping a package using ground shipping premium
grd_ship_premium = 125.0 

shipping_price = grd_ship_premium
print('Price for shipping with premium service:', shipping_price)

#Cost of shipping with Drone where flat charge is 0


if weight <= 2:
  shipping_price = weight * 4.50 
  print('drone_shipping_price:', shipping_price)
elif weight <= 6:
  shipping_price = weight * 9.00 
  print('drone_shipping_price:', shipping_price)
elif weight <= 10:
  shipping_price = weight * 12.00 
  print('drone_shipping_price:', shipping_price)
else:
  shipping_price = weight * 14.25 
  print('drone_shipping_price:', shipping_price) 




