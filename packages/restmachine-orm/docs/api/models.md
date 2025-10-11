# Models API

## Model

::: restmachine_orm.Model
    options:
      show_root_heading: true
      show_source: true

## Field

::: restmachine_orm.Field
    options:
      show_root_heading: true
      show_source: false

## Decorators

### partition_key

::: restmachine_orm.partition_key
    options:
      show_root_heading: true
      show_source: true

### sort_key

::: restmachine_orm.sort_key
    options:
      show_root_heading: true
      show_source: true

## DynamoDB-Specific Decorators

The following decorators are available for DynamoDB backend (in `restmachine_orm.models.decorators`):

- `gsi_partition_key(index_name)` - Mark method as GSI partition key generator
- `gsi_sort_key(index_name)` - Mark method as GSI sort key generator

These are used with the DynamoDB backend to define Global Secondary Index keys. See the [DynamoDB Backend documentation](../backends/dynamodb.md) for usage examples.
