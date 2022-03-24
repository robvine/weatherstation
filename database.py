from mysql.connector import connect, Error

try:
    with connect(
        host="localhost",
        user='weatheruser',
        password='weatherpass',
        database='weather',
    ) as connection:
        db_query = "CREATE DATABASE online_movie_rating"
        with connection.cursor() as cursor:
            cursor.execute(create_db_query)

except Error as e:
    print(e)
