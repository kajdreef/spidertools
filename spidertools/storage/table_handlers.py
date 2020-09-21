import sqlite3
import sys
from typing import Dict

# Abstact class
class TableHandler():
    def __init__(self, database_location: str):
        self._conn = sqlite3.connect(database_location)

    def create(self, sql):
        c = self._conn.cursor()
        c.execute(sql)
        self._conn.commit()

    def select(self, sql, values=()):
        c = self._conn.cursor()
        c.row_factory = sqlite3.Row
        c.execute(sql, values)
        
        if (result := c.fetchone()) is None:
            return None
        else:
            return dict(result)

    def select_all(self, sql, values=()):
        c = self._conn.cursor()
        c.row_factory = sqlite3.Row
        c.execute(sql, values)

        if (result := c.fetchall()) is None:
            return None
        else:
            return [dict(row) for row in result]


    def insert(self, sql, values=()):
        c = self._conn.cursor()
        c.execute(sql, values)
        self._conn.commit()

        return c.lastrowid

    def close(self):
        self._conn.close()


class ProjectTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)
        CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS Projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT UNIQUE
        );
        """

        self.create(CREATE_TABLE)

    def add_project(self, project_name):
        return self.insert('''INSERT INTO Projects( project_name ) VALUES (?) ''', (project_name, ))

    def get_project_id(self, project_name) -> int:
        return self.select('''SELECT project_id FROM Projects WHERE project_name=?''', (project_name, ))

    def get_projects(self):
        return self.select_all('''SELECT project_name FROM Projects''')

class CommitTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)
        CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS Commits (
            commit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            commit_sha TEXT NOT NULL,
            FOREIGN KEY( project_id ) REFERENCES Projects ( project_id )
        );
        """

        self.create(CREATE_TABLE)

    def add_commit(self, project_id, commit_sha):
        return self.insert('''INSERT INTO Commits( project_id, commit_sha ) VALUES (?, ?) ''', (project_id, commit_sha))

    def get_commit_id(self, project_id, commit_sha):
        return self.select('''SELECT commit_id FROM Commits WHERE project_id=? AND commit_sha=?''', (project_id, commit_sha))

    def get_all_commits(self, project_id:int):
        return self.select_all('''SELECT commit_sha FROM Commits WHERE project_id=?''', (int(project_id),))

class BuildTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)

        CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS BuildResults (
            commit_id INTEGER,
            build_passed BOOLEAN,
            FOREIGN KEY ( commit_id ) REFERENCES Commits( commit_id ),
            PRIMARY KEY ( commit_id )
        );
        """

        self.create(CREATE_TABLE)

    def add_build_result(self, commit_id: int, build_passed: bool):
        return self.insert('''INSERT INTO BuildResults( commit_id, build_passed ) VALUES (?, ?) ''', (commit_id, build_passed))

class ProductionMethodTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)

        CREATE_METHOD_TABLE = """
        CREATE TABLE IF NOT EXISTS ProductionMethods (
            method_id INTEGER,
            project_id INTEGER,
            method_name TEXT,
            method_decl TEXT,
            class_name TEXT,
            package_name TEXT,
            PRIMARY KEY ( project_id, method_name, method_decl, class_name, package_name )
        );
        """

        CREATE_COMMIT_METHODS_TABLE = """
        CREATE TABLE IF NOT EXISTS CommitMethodLinkTable (
            method_id INTEGER,
            commit_id INTEGER,
            FOREIGN KEY ( commit_id ) REFERENCES Commits( commit_id ),
            FOREIGN KEY ( method_id ) REFERENCES ProductionMethods( rowid ),
            PRIMARY KEY ( method_id, commit_id)
        );
        """

        self.create(CREATE_METHOD_TABLE)
        self.create(CREATE_COMMIT_METHODS_TABLE)

    def add_production_method(self, project_id: int, commit_id: int, method_name: str, method_decl: str, class_name: str, package_name: str):
        # sys.maxsize + 1 is added so all numbers are positive numbers.
        method_id = hash((project_id, method_name, method_decl, class_name, package_name))  % ((sys.maxsize + 1) )

        try:
            self.insert('''
                INSERT INTO ProductionMethods( method_id, project_id, method_name, method_decl, class_name, package_name ) 
                VALUES (?, ?, ?, ?, ?, ?) ''', 
                (method_id, project_id, method_name, method_decl, class_name, package_name)
            )
        except:
            pass

        try:
            self.insert ('''INSERT INTO CommitMethodLinkTable ( method_id, commit_id ) VALUES (?, ?) ''', (method_id, commit_id))
        except:
            pass
        return method_id

    def get_method_id(self, project_id, method_name, method_decl, class_name, package_name):
        return self.select('''
            SELECT rowid FROM ProductionMethods 
            WHERE project_id=?
                AND method_name=? 
                AND method_decl=?
                AND class_name=?
                AND package_name=?        
        ''', (project_id, method_name, method_decl, class_name, package_name))
    
    def get_all_methods(self, commit_id):
        return self.select_all('''
            SELECT ProductionMethods.method_id, method_name, method_decl, class_name, package_name FROM ProductionMethods
            INNER JOIN CommitMethodLinkTable
            ON ProductionMethods.method_id=CommitMethodLinkTable.method_id
            WHERE commit_id=?
        ''', (commit_id, ))

class TestMethodTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)

        CREATE_TEST_METHOD_TABLE = """
        CREATE TABLE IF NOT EXISTS TestMethods (
            test_id INTEGER UNIQUE,
            project_id INTEGER,
            method_name TEXT,
            class_name TEXT,
            PRIMARY KEY (project_id, method_name, class_name)
        );
        """

        CREATE_COMMIT_TEST_METHOD_LINK_TABLE = """
        CREATE TABLE IF NOT EXISTS CommitTestMethodLinkTable (
            test_id INTEGER,
            commit_id INTEGER,
            test_result BOOLEAN,
            FOREIGN KEY ( test_id ) REFERENCES TestMethods( rowid ),
            FOREIGN KEY ( commit_id ) REFERENCES Commits( commit_id ),
            PRIMARY KEY ( test_id, commit_id)
        );
        """

        self.create(CREATE_TEST_METHOD_TABLE)
        self.create(CREATE_COMMIT_TEST_METHOD_LINK_TABLE)

    def add_test_method(self, project_id: int, commit_id: int, class_name: str, method_name: str, test_result: bool):
        # sys.maxsize + 1 is added so all numbers are positive numbers.
        test_id = hash((project_id, method_name, class_name)) % ((sys.maxsize + 1))
        try:
            self.insert('''INSERT INTO TestMethods( test_id, project_id, method_name, class_name ) VALUES (?, ?, ?, ?) ''', (test_id, project_id, method_name, class_name))
        except:
            pass

        try:
            self.insert('''INSERT INTO CommitTestMethodLinkTable ( test_id, commit_id, test_result ) VALUES (?, ?, ?) ''', (test_id, commit_id, test_result))
        except:
            pass
        
        return test_id

    def get_test_method_id(self, project_id, test_name, class_name):
        return self.select('''
            SELECT test_id FROM TestMethods
            WHERE project_id=?
            test_name=?
            class_name=?
            ''', (project_id, test_name, class_name))

    def get_all_methods(self, commit_id):
        return self.select_all('''
            SELECT TestMethods.test_id, method_name, class_name, CommitTestMethodLinkTable.test_result FROM TestMethods
            INNER JOIN CommitTestMethodLinkTable
            ON TestMethods.test_id=CommitTestMethodLinkTable.test_id
            WHERE commit_id=?
        ''', (commit_id, ))

class MethodCoverageTableHandler(TableHandler):
    def __init__(self, database_location):
        super().__init__(database_location)

        CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS MethodCoverage (
            method_id INTEGER,
            test_id INTEGER,
            commit_id INTEGER,
            FOREIGN KEY ( commit_id ) REFERENCES Commits( commit_id ),
            FOREIGN KEY ( test_id ) REFERENCES TestMethods( test_id ),
            FOREIGN KEY ( method_id ) REFERENCES ProductionMethods( method_id ),
            PRIMARY KEY (method_id, test_id, commit_id)
        );
        """
        self.create(CREATE_TABLE)
    
    def add_coverage(self, method_id, test_id, commit_id):
        try:
            return self.insert('''INSERT INTO MethodCoverage ( method_id, test_id, commit_id ) VALUES (?, ?, ?) ''', (method_id, test_id, commit_id))
        except:
            return None

    def get_all_coverage(self, commit_id):
        return self.select_all('''
        SELECT method_id, test_id FROM MethodCoverage
        WHERE commit_id=?
        ''', (commit_id, ))

class MethodCoverageHandler():

    def __init__(self, database_location):
        self.prod_method_table = ProductionMethodTableHandler(database_location)
        self.test_method_table = TestMethodTableHandler(database_location)
        self.cov_method_table = MethodCoverageTableHandler(database_location)

    def add_project_coverage(self, project_id: int, commit_id: int, prod_methods, test_methods):
        test_id_map : Dict = {}

        for method in test_methods:
            # TODO: test methods should be described my class name + method name.
            # PROBLEM: we currently map 'global' method_id to 'local' test_id (unique per commit), so create a map of local test_id to global test_id store only global ID in database.
            global_test_id = self.test_method_table.add_test_method(project_id, commit_id, method["method_name"], method["class_name"], method["test_result"])
            
            test_id_map[method['test_id']] = global_test_id
            # if (test_id := method["test_id"]) is not None and test_id in test_id_map:
            #     test_id_map[test_id] = global_test_id

        for method in prod_methods:
            prod_method_id = self.prod_method_table.add_production_method(project_id, commit_id, method["methodName"], method["methodDecl"], method["className"], method["packageName"])

            for test_id in method['test_ids']:
                if test_id in test_id_map:
                    self.cov_method_table.add_coverage(prod_method_id, test_id_map[test_id], commit_id)
                elif (len(test_methods)) == 0:
                    continue
                else:
                    exit(1)

    def get_project_coverage(self, commit_id: int):
        return {
            'methods': self.prod_method_table.get_all_methods(commit_id),
            'tests': self.test_method_table.get_all_methods(commit_id),
            'links': self.cov_method_table.get_all_coverage(commit_id)
        }

    def close(self):
        self.prod_method_table.close()
        self.test_method_table.close()
        self.cov_method_table.close()