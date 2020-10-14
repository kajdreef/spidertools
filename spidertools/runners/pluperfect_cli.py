import argparse
import os
from sqlalchemy.sql.sqltypes import Boolean
import yaml
import json
from typing import Tuple
from spidertools.utils.analysis_repo import AnalysisRepo
from spidertools.tools.tacoco import TacocoRunner
from spidertools.tools.history import MethodParserRunner
from spidertools.storage.db_helper import DatabaseHelper
from spidertools.storage.parsing.methods import MethodParser
from spidertools.storage.parsing.tacoco import TacocoParser
from spidertools.storage.models.repository import Commit, Project

# By default the database is only created in memory
DB_PATH = ":memory:"

def parse_arguments():
    """
    Parse arguments to run pluperfect
    """
    parser = argparse.ArgumentParser(description='Run Tacoco')

    # TODO: Add option to switch between number of releases and number of commits
    parser.add_argument('project_url', type=str, help="Absolute path or url to system-under-test.")
    parser.add_argument('--output_path', type=str, help="absolute path to output directory")
    parser.add_argument('--current', action='store_true', help="Run the analysis on current version of the code")
    parser.add_argument('--config', type=str, help="absolute path to tacoco")

    return parser.parse_args()

def start(project_url, output_path, tacoco_path, history_slider_path, single_run):
    global DB_PATH

    db_handler = DatabaseHelper(DB_PATH)

    with AnalysisRepo(project_url) as repo:
        # TODO Add in error handling for existing commits/projects
        print(f"[INFO] Project: {repo.get_project_name()}")

        # Add project
        project = Project(project_name=repo.get_project_name())
        # with db_handler.create_session() as session:
        #     project, new_project = session.add(project)
        
        # Analysis tools
        tacoco_runner = TacocoRunner(repo, output_path, tacoco_path)
        parser_runner = MethodParserRunner(repo, output_path, history_slider_path)

        # Get all commits we want to run the analysis on.
        commits = []
        if single_run:
            commits = [repo.get_current_commit()]
        else:
            commits = repo.iterate_tagged_commits(5)
        
        for commit in commits:
            print(f"[INFO] Analyze commit: {commit}")
            # Add commit to the database
            commit = Commit(sha=commit)

            # Run analysis and return paths to output files
            success, method_file_path, tacoco_file_path = _analysis(repo, tacoco_runner, parser_runner, output_path)
            
            if not success:
                print(f'[Error] Analysis for {commit} failed...')

            with open(method_file_path) as method_file:
                method_parser = MethodParser()\
                    .set_commit(commit)

                coverage = method_parser\
                    .parse(json.load(method_file))
                method_parser.store(
                    db_helper=db_handler,
                    project=project,
                    commit=commit,
                    methods=coverage
                )

            with open(tacoco_file_path) as tacoco_file:
                tacoco_parser = TacocoParser()
                coverage = tacoco_parser\
                    .parse(json.load(tacoco_file))

                tacoco_parser.store(
                    db_helper=db_handler,
                    project=project,
                    commit=commit,
                    coverage=coverage
                )

def _analysis(repo, tacoco_runner, parser_runner, output_path) -> Tuple[Boolean, str, str]:
    # Before each analysis remove all generated files of previous run
    repo.clean()

    # Start analysis
    build_output = tacoco_runner.build()

    if build_output != 1:
        parser_runner.run()
        tacoco_runner.run()

        # Combine data
        commit_sha = repo.get_current_commit()
        project_output_path = f"{output_path}{os.path.sep}{repo.get_project_name()}{os.path.sep}"

        print("[Info] build successfull...")
        return (True,
            f"{project_output_path}methods-{commit_sha}.json",
            f"{project_output_path}{commit_sha}-cov-matrix.json"
        )

    print("[ERROR] build failure...")
    return (False, None, None)

def main():
    """
    pluperfect - Run per test case coverage and method parsing on a project for a set of commits.
    """
    print("Start analysis...")
    global DB_PATH

    arguments = parse_arguments()
    project_url = arguments.project_url
    config_path = arguments.config

    if config_path is not None:
        with open(config_path) as config_file:
            config = yaml.safe_load(config_file.read())

        analysis_config = config["analysis"]
        output_path = f"{os.getcwd()}{os.path.sep}"
        DB_PATH = analysis_config["DB_LOCATION"]
        if analysis_config["OUTPUT_DIR"]:
            output_path = analysis_config["OUTPUT_DIR"]
        tacoco_path = analysis_config["TACOCO_HOME"]
        history_slider_path = analysis_config["HISTORY_SLICER_HOME"]
    else:
        print("Provide config path...")
        exit(1)

    start(project_url, output_path, tacoco_path, history_slider_path, single_run=arguments.current)
