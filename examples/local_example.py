#!/usr/bin/env python3
"""
Multi-Server Comparison Example

This example demonstrates how to run the same RestMachine application
with different HTTP servers and configurations to compare their behavior.

This is useful for testing and benchmarking different server setups.
"""

import sys
import logging
from typing import Optional
from pydantic import BaseModel
from restmachine import RestApplication

logging.basicConfig(level=logging.WARNING)

app = RestApplication()

class User(BaseModel):
    id: str
    name: str
    email: str
    age: Optional[int] = None

class CreateUser(BaseModel):
    name: str
    email: str

users_db = {}

@app.dependency()
def user_database():
    return users_db

@app.validates
def create_user_request(json_body) -> CreateUser:
    return CreateUser.model_validate(json_body)


@app.generate_etag
def user_etag(user):
    if user:
        return user.id

@app.resource_exists
def user(path_params, user_database) -> User:
    user = user_database.get(path_params.get("user_id"))
    if user is None:
        return None
    return User(**user)

@app.get("/users")
def list_users(user_database) -> list[User]:
    users = [User(**u) for u in user_database.values()]
    return users

@app.post("/users")
def create_user(user_database, create_user_request) -> User:
    keys = list(user_database.keys())
    if keys:
        last_key = keys[-1]
        new_id = str(int(last_key)+1)
    else:
        new_id = "1"

    new_user = User(**create_user_request.model_dump(), id=new_id)
    user_database[new_id] = new_user.model_dump()
    return new_user

@app.get("/users/{user_id}")
def get_user(user) -> User:
    return user

@app.delete("/users/{user_id}")
def delete_user(user_database, user) -> None:
    del user_database[user.id]



def main():
    from restmachine.servers import UvicornDriver
    driver = UvicornDriver(
        app,
        host="127.0.0.1",
        port=8080,
        http_version='http1'
    )
    #from restmachine.servers import HypercornDriver
    #driver = HypercornDriver(
    #    app,
    #    host="127.0.0.1",
    #    port=port,
    #    http_version='http2'
    #)
    if driver.is_available():
        driver.run(log_level="error", workers=1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nError running benchmark: {e}")
        sys.exit(1)
