# Microservices Application README

This repository contains a microservices application with two main services: `user_service` for user CRUD operations and `auth_service` for authentication. The application uses an event-driven architecture with RabbitMQ to synchronize user data between the services.

## How to Run

To run the application, you need to have Docker and Docker Compose installed. Once you have them, you can run the following command in the root directory of the project:

```bash
docker-compose up -d
```

This will start all the services in the background. To stop the services, you can run:

```bash
docker-compose down
```

## API Endpoints

### User Service (`user_service`)

The `user_service` is responsible for handling user data. It provides the following endpoints:

#### Create User

* **Endpoint:** `POST /users`
* **Description:** Creates a new user.
* **Request Body:**
  ```json
  {
    "username": "testuser",
    "password": "testpassword"
  }
  ```
* **Response:**
  ```json
  {
    "id": 1,
    "username": "testuser"
  }
  ```

#### Get Users

* **Endpoint:** `GET /users`
* **Description:** Retrieves a list of users.
* **Response:**
  ```json
  [
    {
      "id": 1,
      "username": "testuser"
    }
  ]
  ```

#### Get User

* **Endpoint:** `GET /users/{user_id}`
* **Description:** Retrieves a single user by their ID.
* **Response:**
  ```json
  {
    "id": 1,
    "username": "testuser"
  }
  ```

#### Update User

* **Endpoint:** `PUT /users/{user_id}`
* **Description:** Updates a user's information.
* **Request Body:**
  ```json
  {
    "username": "newusername"
  }
  ```
* **Response:**
  ```json
  {
    "id": 1,
    "username": "newusername"
  }
  ```

#### Delete User

* **Endpoint:** `DELETE /users/{user_id}`
* **Description:** Deletes a user by their ID.
* **Response:**
  ```json
  {
    "id": 1,
    "username": "newusername"
  }
  ```

### Authentication Service (`auth_service`)

The `auth_service` is responsible for handling user authentication. It provides the following endpoints:

#### Login

* **Endpoint:** `POST /login`
* **Description:** Authenticates a user and returns a JWT token.
* **Request Body:**
  ```json
  {
    "username": "testuser",
    "password": "testpassword"
  }
  ```
* **Response:**
  ```json
  {
    "token": "your.jwt.token"
  }
  ```

#### Logout

* **Endpoint:** `POST /logout`
* **Description:** Logs out a user by invalidating their JWT token.
* **Headers:**
  ```
  Authorization: Bearer your.jwt.token
  ```
* **Response:**
  ```json
  {
    "status": "logout successful"
  }
  ```
