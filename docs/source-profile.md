# Source data profile

## couriers (3 rows)

| column | type | null % | distinct |
|---|---|---|---|
| id | int | 0.0 | 3 |
| name | varchar | 0.0 | 3 |
| createdAt | datetime | 0.0 | 1 |
| updatedAt | datetime | 0.0 | 1 |

## orderitems (1,999,824 rows)

| column | type | null % | distinct |
|---|---|---|---|
| quantity | int | 0.0 | 10 |
| notes | varchar | 100.0 | 0 |
| createdAt | datetime | 0.0 | 433 |
| updatedAt | datetime | 0.0 | 433 |
| OrderId | int | 0.0 | 1,000,000 |
| ProductId | int | 0.0 | 10,000 |

## orders (1,000,000 rows)

| column | type | null % | distinct |
|---|---|---|---|
| id | int | 0.0 | 1,000,000 |
| orderNumber | varchar | 0.0 | 1,000,000 |
| userId | int | 0.0 | 99,996 |
| deliveryDate | varchar | 0.0 | 730 |
| deliveryRiderId | int | 0.0 | 100 |
| createdAt | datetime | 0.0 | 433 |
| updatedAt | datetime | 0.0 | 433 |

## products (10,000 rows)

| column | type | null % | distinct |
|---|---|---|---|
| id | int | 0.0 | 10,000 |
| productCode | varchar | 0.0 | 10,000 |
| category | varchar | 0.0 | 12 |
| description | varchar | 0.0 | 9,984 |
| name | varchar | 0.0 | 6,251 |
| price | float | 0.0 | 9,949 |
| createdAt | datetime | 0.0 | 3 |
| updatedAt | datetime | 0.0 | 3 |

## riders (100 rows)

| column | type | null % | distinct |
|---|---|---|---|
| id | int | 0.0 | 100 |
| firstName | varchar | 0.0 | 98 |
| lastName | varchar | 0.0 | 95 |
| vehicleType | varchar | 0.0 | 6 |
| courierId | int | 0.0 | 3 |
| age | int | 0.0 | 36 |
| gender | varchar | 0.0 | 4 |
| createdAt | datetime | 0.0 | 1 |
| updatedAt | datetime | 0.0 | 1 |

## users (100,000 rows)

| column | type | null % | distinct |
|---|---|---|---|
| id | int | 0.0 | 100,000 |
| username | varchar | 0.0 | 100,000 |
| firstName | varchar | 0.0 | 3,005 |
| lastName | varchar | 0.0 | 5,540 |
| address1 | varchar | 0.0 | 99,882 |
| address2 | varchar | 0.0 | 1,800 |
| city | varchar | 0.0 | 60,396 |
| country | varchar | 0.0 | 249 |
| zipCode | varchar | 0.0 | 89,318 |
| phoneNumber | varchar | 0.0 | 100,000 |
| dateOfBirth | varchar | 0.0 | 730 |
| gender | varchar | 0.0 | 4 |
| createdAt | datetime | 0.0 | 24 |
| updatedAt | datetime | 0.0 | 24 |
