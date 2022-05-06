from getpass import getpass
from sys import exit, stderr
from os import path
from json import dump, load
from base64 import b64decode
from typing import List
from pymongo.database import Database as MongoDatabase
from pymongo.collection import Collection as MongoCollection
from pymongo.mongo_client import MongoClient
from pymongo import ASCENDING
import mysql.connector
from urllib.parse import quote_plus
from colorama import Fore


from .credentials import RawCredential, Credential
from .passwords import encrypt_and_encode, generate_salt
from .validator import ensure_type


class DbConfig:
    def __init__(self, host: str, user: str, password: str, db: str, port: int | None = None):
        self.host = host
        self.user = user
        self.password = password
        self.db = db
        self.port = port
class MysqlManager:
    mysql_db: mysql.connector.MySQLConnection | None = None
    mysql_cursor: any = None

    def __init__(self,  db_config: DbConfig):
        try:
            self.mysql_db: mysql.connector.MySQLConnection = mysql.connector.connect(
                host=db_config.host,
                user=db_config.user,
                password=db_config.password,
                db=db_config.db,
                port=db_config.port if db_config.port else 3306,
                connection_timeout=3
            )
            self.mysql_cursor = self.mysql_db.cursor()
        except Exception as e:
            print()
            print(f"{Fore.RED}There was an error while connecting with MySQL:", file=stderr)
            print(str(e), file=stderr)
            print()
            print(f"Exiting with code 1!{Fore.RESET}", file=stderr)
            exit(1)

    def add_credential(self, title: str, username: str, email: str, password: str, salt: str) -> None:
        """This method takes in the encrypted and encoded credentials and adds them to the database."""
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(password, str, "password", "string")
        ensure_type(salt, str, "salt", "string")

        # Add the password to the database
        try:
            self.mysql_cursor.execute(
                "INSERT INTO credentials(title, username, email, password, salt) VALUES(%s, %s, %s, %s, %s);",
                (title, username, email, password, salt)
            )
            self.mysql_db.commit()
        except Exception as e:
            print("There was an error while adding the credential:", file=stderr)
            print(e, file=stderr)

    def get_all_credentials(self) -> List[RawCredential] | None:
        try:
            raw_creds: List[RawCredential] = []

            self.mysql_cursor.execute("SELECT * FROM credentials WHERE title LIKE '%' AND username LIKE '%' AND email LIKE '%'")
            for i in self.mysql_cursor.fetchall():
                raw_creds.append(RawCredential(i[0], i[1], i[2], i[3], i[4], i[5]))

            return raw_creds
        except Exception as e:
            print("There was an error while getting the credentials:", file=stderr)
            print(e)
            return None

    def get_credential(self, id: int) -> RawCredential | None:
        ensure_type(id, int, "id", "int")

        self.mysql_cursor.execute("SELECT * FROM credentials WHERE id = %s", (id, ))
        query_result = self.mysql_cursor.fetchone()
        if not query_result:
            return None
        return RawCredential(
            query_result[0],
            query_result[1],
            query_result[2],
            query_result[3],
            query_result[4]
        )

    def remove_credential(self, id: int) -> None:
        ensure_type(id, int, "id", "int")
        if not id:
            raise ValueError("Invalid value provided for parameter 'id'")

        self.mysql_cursor.execute("DELETE FROM credentials WHERE id=%s", (id, ))
        self.mysql_db.commit()

    def remove_all_credentials(self) -> None:
        self.mysql_cursor.execute("DELETE FROM credentials")
        self.mysql_db.commit()

    def modify_credential(self, id: int, title: str, username: str, email: str, password: str, salt: str) -> None:
        ensure_type(id, int, "id", "int")
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(password, str, "password", "string")
        ensure_type(salt, str, "salt", "string")

        self.mysql_cursor.execute("UPDATE credentials SET title = %s, username = %s, email = %s, password = %s, salt = %s WHERE id = %s", (
            title, username, email, password, salt, id))
        self.mysql_db.commit()

    def filter_credentials(self, title: str, username: str, email: str, master_pass: str) -> List[Credential]:
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(master_pass, str, "master_pass", "string")

        raw_creds: List[RawCredential] = self.get_all_credentials()
        if raw_creds == []:
            return raw_creds

        filtered_creds: List[Credential] = []
        for raw_cred in raw_creds:
            cred = raw_cred.get_credential(master_pass)
            title_match = title.lower() in cred.title.lower()
            username_match = username.lower() in cred.username.lower()
            email_match = email.lower() in cred.email.lower()

            if title_match and username_match and email_match:
                filtered_creds.append(cred)

        return filtered_creds

    def execute_raw_query(self, query: str) -> None:
        ensure_type(query, str, "query", "string")

        # Exception Handling
        if not query:
            raise ValueError("Parameter 'query' cannot be empty")

        try:
            self.mysql_cursor.execute(query)
            self.mysql_db.commit()
            return self.mysql_cursor.fetchall()
        except Exception as e:
            print("There was an error while executing a query: ")
            print("Query: ", query)
            print("Error: ", e)
            print("Exiting!")
            exit(1)

    def export_to_file(self, file_path: str, master_pass: str, file_master_pass: str) -> None:
        ensure_type(file_path, str, "filename", "string")
        ensure_type(master_pass, str, "master_pass", "string")
        ensure_type(file_master_pass, str, "file_master_pass", "string")

        if not file_path:
            raise ValueError("Invalid value provided for parameter 'filename'")

        raw_creds: List[RawCredential] = self.get_all_credentials()
        if not raw_creds:
            print("No credentials to export.")
            return

        cred_objs = []

        for raw_cred in raw_creds:
            salt = b64decode(raw_cred.salt)
            cred = raw_cred.get_credential(master_pass)

            cred_objs.append({
                "id": cred.id,
                "title": encrypt_and_encode(file_master_pass, cred.title, salt),
                "username": encrypt_and_encode(file_master_pass, cred.username, salt),
                "email": encrypt_and_encode(file_master_pass, cred.email, salt),
                "password": encrypt_and_encode(file_master_pass, cred.password, salt),
                "salt": raw_cred.salt,
            })

        dump(cred_objs, open(file_path, "w"))

    def import_from_file(self, master_pass, filename: str) -> None:
        ensure_type(master_pass, str, "master_password", "string")
        ensure_type(filename, str, "filename", "string")

        if not filename:
            raise ValueError("Invalid value provided for parameter 'filename'")

        if not path.isfile(filename):
            print(f"{filename} does not exist!")
            raise Exception

        file_master_pass: str = getpass("Input master password for file: ")
        file_creds = load(open(filename, "r"))

        if not file_creds:
            print("There are no credentials in the file.")

        print("\nBegin importing file credentials...")

        for file_cred in file_creds:
            # TODO: Rather than decrypting them manually, use the RawCredential class to get_credential. This will give more output to user

            raw_cred = RawCredential(
                id=file_cred["id"],
                title=file_cred["title"],
                username=file_cred["username"],
                email=file_cred["email"],
                password=file_cred["password"],
                salt=file_cred["salt"],
            )

            salt = generate_salt(16)

            new_cred = raw_cred.get_credential(file_master_pass).get_raw_credential(master_pass, salt)

            self.add_credential(
                new_cred.title,
                new_cred.username,
                new_cred.email,
                new_cred.password,
                new_cred.salt,
            )

            print(f"{Fore.GREEN}Credential added.{Fore.RESET}")
            print()

    def close(self):
        try:
            if self.mysql_cursor:
                self.mysql_cursor.close()
            if self.mysql_db:
                self.mysql_db.close()

        except Exception as e:
            print("There was an error while closing the connection:", file=stderr)
            print(e, file=stderr)

    def __del__(self):
        self.close()
class MongoManager:
    mongo_db: MongoDatabase | None = None
    mongo_client: MongoClient | None = None
    mongo_collection: MongoCollection | None = None

    def __init__(self,  db_config: DbConfig):
        try:
            self.mongo_client = MongoClient(
                host=quote_plus(db_config.host),
                username=quote_plus(db_config.user) if db_config.user and db_config.password else None,
                password=quote_plus(db_config.password) if db_config.user and db_config.password else None,
                port=db_config.port if db_config.port else None,
                authSource=db_config.db,
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                socketTimeoutMS=3000
            )
            self.mongo_client.server_info()  # To make sure that the mongo instance is valid
            self.mongo_db = self.mongo_client[db_config.db]
            self.mongo_collection = self.mongo_db["credentials"]

            self.mongo_collection.create_index([("id", ASCENDING)], unique=True)
        except Exception as e:
            print()
            print(f"{Fore.RED}There was an error while connecting with MongoDB:", file=stderr)
            print(str(e), file=stderr)
            print()
            print(f"Exiting with code 1!{Fore.RESET}", file=stderr)
            exit(1)

    def __gen_id(self) -> int | None:
        """This method will generate a unique id for the credential. Note: To be used only with MongoDB"""
        id = self.mongo_collection.estimated_document_count() + 1
        while self.get_credential(id):
            id += 1
        return id

    def add_credential(self, title: str, username: str, email: str, password: str, salt: str) -> None:
        """This method takes in the encrypted and encoded credentials and adds them to the database."""
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(password, str, "password", "string")
        ensure_type(salt, str, "salt", "string")

        # Encode to b64
        id = self.__gen_id()

        # Add the password to the database
        try:
            self.mongo_collection.insert_one({
                "id": id,
                "title": title,
                "username": username,
                "email": email,
                "password": password,
                "salt": salt
            })
        except Exception as e:
            print("There was an error while adding the credential:", file=stderr)
            print(e, file=stderr)

    def get_all_credentials(self) -> List[RawCredential] | None:
        try:
            raw_creds: List[RawCredential] = []

            for i in self.mongo_collection.find():
                raw_creds.append(RawCredential(i["id"], i["title"], i["username"], i["email"], i["password"], i["salt"]))

            return raw_creds
        except Exception as e:
            print("There was an error while getting the credentials:", file=stderr)
            print(e)
            return None

    def get_credential(self, id: int) -> RawCredential | None:
        ensure_type(id, int, "id", "int")

        query_result = self.mongo_collection.find_one({"id": id})
        if not query_result:
            return None
        return RawCredential(
            query_result["id"],
            query_result["title"],
            query_result["username"],
            query_result["email"],
            query_result["password"],
            query_result["salt"]
        )

    def remove_credential(self, id: int) -> None:
        ensure_type(id, int, "id", "int")

        self.mongo_collection.delete_one({"id": id})

    def remove_all_credentials(self) -> None:
        self.mongo_collection.delete_many({})

    def modify_credential(self, id: int, title: str, username: str, email: str, password: str, salt: str) -> None:
        ensure_type(id, int, "id", "int")
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(password, str, "password", "string")
        ensure_type(salt, str, "salt", "string")

        self.mongo_collection.update_one({"id": id}, {"$set": {
            "title": title,
            "username": username,
            "email": email,
            "password": password,
            "salt": salt
        }})

    def filter_credentials(self, title: str, username: str, email: str, master_pass: str) -> List[Credential]:
        ensure_type(title, str, "title", "string")
        ensure_type(username, str, "username", "string")
        ensure_type(email, str, "email", "string")
        ensure_type(master_pass, str, "master_pass", "string")

        raw_creds: List[RawCredential] = self.get_all_credentials()
        if raw_creds == []:
            return raw_creds

        filtered_creds: List[Credential] = []
        for raw_cred in raw_creds:
            cred = raw_cred.get_credential(master_pass)
            title_match = title.lower() in cred.title.lower()
            username_match = username.lower() in cred.username.lower()
            email_match = email.lower() in cred.email.lower()

            if title_match and username_match and email_match:
                filtered_creds.append(cred)

        return filtered_creds

    def export_to_file(self, file_path: str, master_pass: str, file_master_pass: str) -> None:
        ensure_type(file_path, str, "filename", "string")
        ensure_type(master_pass, str, "master_pass", "string")
        ensure_type(file_master_pass, str, "file_master_pass", "string")

        if not file_path:
            raise ValueError("Invalid value provided for parameter 'filename'")

        raw_creds: List[RawCredential] = self.get_all_credentials()
        if not raw_creds:
            print("No credentials to export.")
            return

        cred_objs = []

        for raw_cred in raw_creds:
            salt = b64decode(raw_cred.salt)
            cred = raw_cred.get_credential(master_pass)

            cred_objs.append({
                "id": cred.id,
                "title": encrypt_and_encode(file_master_pass, cred.title, salt),
                "username": encrypt_and_encode(file_master_pass, cred.username, salt),
                "email": encrypt_and_encode(file_master_pass, cred.email, salt),
                "password": encrypt_and_encode(file_master_pass, cred.password, salt),
                "salt": raw_cred.salt,
            })

        dump(cred_objs, open(file_path, "w"))

    def import_from_file(self, master_pass, filename: str) -> None:
        ensure_type(master_pass, str, "master_password", "string")
        ensure_type(filename, str, "filename", "string")

        if not filename:
            raise ValueError("Invalid value provided for parameter 'filename'")

        if not path.isfile(filename):
            print(f"{filename} does not exist!")
            raise Exception

        file_master_pass: str = getpass("Input master password for file: ")
        file_creds = load(open(filename, "r"))

        if not file_creds:
            print("There are no credentials in the file.")

        print("\nBegin importing file credentials...")

        for file_cred in file_creds:
            # TODO: Rather than decrypting them manually, use the RawCredential class to get_credential. This will give more output to user

            raw_cred = RawCredential(
                id=file_cred["id"],
                title=file_cred["title"],
                username=file_cred["username"],
                email=file_cred["email"],
                password=file_cred["password"],
                salt=file_cred["salt"],
            )

            salt = generate_salt(16)

            new_cred = raw_cred.get_credential(file_master_pass).get_raw_credential(master_pass, salt)

            self.add_credential(
                new_cred.title,
                new_cred.username,
                new_cred.email,
                new_cred.password,
                new_cred.salt,
            )

            print(f"{Fore.GREEN}Credential added.{Fore.RESET}")
            print()

    def close(self):
        try:
            if self.mongo_client:
                self.mongo_client.close()
        except Exception as e:
            print("There was an error while closing connection with MongoDB:", file=stderr)
            print(e, file=stderr)

    def __del__(self):
        self.close()
