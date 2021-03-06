import re

from sqlalchemy.sql.sqltypes import Boolean
from spidertools.storage.db_helper import DatabaseHelper
from typing import Dict, List, Tuple
from spidertools.storage.models.methods import ProdMethod, ProdMethodVersion, TestMethod, LineCoverage
from spidertools.storage.models.repository import Commit, Project
import logging

logger = logging.getLogger(__name__)

class TacocoParser():
    def parse(self, tacoco_dict: Dict) -> List[Tuple[TestMethod, LineCoverage]]:
        logger.info("Start parsing tacoco data...")

        # Testcases
        test_map: Dict[int, Tuple[TestMethod, str]] = {}
        if 'testsIndex' in tacoco_dict:
            for idx, test_string in enumerate(tacoco_dict['testsIndex']):
                try:
                    test, result = self.__parse_test_method(test_string)
                except:
                    logger.error("Failed parsing: %s %s", idx, test_string)
                    continue        
                test_map[idx] = (test, result)
        
        # Coverage
        coverage: Dict[int, List[LineCoverage]] = dict()
        if 'sources' in tacoco_dict:
            for source in tacoco_dict['sources']:
                start_line: int = source["source"]["firstLine"]
                
                # create a map from test to covered lines.
                testStmtMatrix = source['testStmtMatrix']
                for test_id, matrix in zip(source['activatingTests'], testStmtMatrix):

                    # Check if test_id is in the map, if not skip it
                    if test_id not in test_map:
                        continue
                    
                    # Create a representation for each line covered by the test
                    for i, covered in enumerate(matrix):
                        line_num = i + start_line

                        #  Skip if not covered
                        if not covered:
                            continue

                        line = LineCoverage(
                            full_name=source["source"]["fullName"],
                            line_number=line_num,
                        )
                        
                        # If test case already in coverage add the line so we know it covers muliple lines.
                        if test_id in coverage:
                            lines = coverage[test_id]
                            lines.append(line)
                            coverage[test_id] = lines
                        else:
                            coverage[test_id] = [line]

        # Merge to dictionaries and return a list of tuples
        def _merge(idx) -> Tuple[TestMethod, str, List[LineCoverage]]:
            test : TestMethod
            result: str
            
            if idx in test_map and idx in coverage:
                test, result = test_map[idx]
                line_coverage: List[LineCoverage] = coverage[idx]

                for line in line_coverage: 
                    line.test_result = result

                return test, line_coverage
            
        result = list(map(_merge, coverage.keys()))
        logger.info("Finished parsing tacoco data...")
        return result

    def _split_file_name(self, method_name: str) -> Tuple[str, str]:
        """
        @param method_name: str 

        """
        path = method_name.split('/')
        class_name = path[len(path) - 1].split('.')[0]
        package_name = '.'.join(path[0 : len(path) - 1])
        return class_name, package_name

    def __parse_test_method(self, test_method: str) -> Tuple[TestMethod, str]:
        # Parsing the class name
        if (result := re.search(r'runner:([a-zA-Z0-9._()$]+)', test_method)) is not None:
            class_name = result.group(1)
        elif (result := re.search(r'class:([a-zA-Z0-9._()$]+)', test_method)) is not None:
            class_name = result.group(1)
        elif (result := re.search(r'[a-zA-Z_0-9]+\(([a-zA-Z_0-9.$]+)\)', test_method)) is not None:
            class_name = result.group(1)
        else:
            logging.error("class_name error: %s", test_method)
            raise Exception("[ERROR] class_name error: {}".format(test_method))

        # Parsing the method name aka test name.
        if (result := re.search(r'test:([a-zA-Z0-9._()$]+)', test_method)) is not None:
            method_name = result.group(1)
        elif (result := re.search(r'method:([a-zA-Z0-9._()$]+)', test_method)) is not None:
            method_name = result.group(1)
        elif (result := re.search(r'test-template:([a-zA-Z0-9._()$]+)', test_method)) is not None:
            method_name = result.group(1)
            invocation_number = re.search(r'test-template-invocation:#([0-9]+)', test_method).group(1)
            method_name = f'{method_name}/{invocation_number}'
        elif (result := re.search(r'([a-zA-Z_0-9]+)\([a-zA-Z_0-9.$]+\)', test_method)) is not None:
            method_name = result.group(1)
        else:
            logging.error("method_name error: %s", test_method)
            raise Exception("[ERROR] method_name error: {}".format(test_method))

        # Parse if test passed or failed
        test_result = "P"
        if (result := re.search(r'(_F$)', test_method) is not None):
            test_result = "F"

        test = TestMethod(class_name=class_name, method_name=method_name)
        return test, test_result

    def store(self,
            db_helper: DatabaseHelper,
            project: Project,
            commit: Commit,
            coverage: List[Tuple[TestMethod, List[LineCoverage]]]
        ):
        with db_helper.create_session() as session:
            project, _ = session.add(project)

            commit.project = project
            commit, _ = session.add(commit)

            for test, lines in coverage:
                test.project = project
                test, _ = session.add(test)

                for line in lines:
                    method_version: ProdMethodVersion = session.query(ProdMethodVersion)\
                        .join(ProdMethod, 
                            (ProdMethod.id==ProdMethodVersion.method_id)
                            & (ProdMethodVersion.line_start <= line.line_number)
                            & (ProdMethodVersion.line_end >= line.line_number)
                        )\
                        .filter(ProdMethod.file_path.contains(line.full_name))\
                        .filter(ProdMethodVersion.commit_id==commit.id)\
                        .first()
                    
                    line.test_id = test.id
                    line.commit_id = commit.id

                    if method_version is None:
                        continue

                    line.method_version_id = method_version.id
                    session.add(line)
