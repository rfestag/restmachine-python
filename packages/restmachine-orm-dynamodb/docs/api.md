# DynamoDB API Reference

## DynamoDBBackend

::: restmachine_orm_dynamodb.DynamoDBBackend
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - create
        - upsert
        - get
        - update
        - delete
        - query
        - batch_create
        - batch_get
        - scan

## DynamoDBAdapter

::: restmachine_orm_dynamodb.DynamoDBAdapter
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - model_to_storage
        - storage_to_model
        - get_primary_key_value

## Testing

### DynamoDBDriver

::: restmachine_orm_dynamodb.testing.DynamoDBDriver
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - execute_create
        - execute_get
        - execute_update
        - execute_delete
        - execute_upsert
        - execute_query
        - count
        - exists
        - clear
        - get_backend_name
        - setup_backend
