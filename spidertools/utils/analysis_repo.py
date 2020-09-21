from git import Repo, Tag, Git
import tempfile
import shutil
import os
from subprocess import Popen

class AnalysisRepo(object):
    def __init__(self, url:str):
        self.url = url
        self.clone_commands = {}
        self.repo: Repo

    def set_depth(self, depth: int) -> 'AnalysisRepo':
        self.clone_commands.update({"depth": depth})
        return self

    def __enter__(self):
        if self.url.startswith("http") or self.url.startswith("https"):
            self.target_dir = tempfile.mkdtemp()
            self._clone()
        else:
            self.target_dir = self.url
            self.repo = Repo(self.target_dir)
        return self

    def _clone(self):
        try:
            self.repo = Repo.clone_from(self.url, self.target_dir, **self.clone_commands)
        except:
            self.repo = Repo(self.target_dir)

        return self

    def __exit__(self, ctx_type, ctx_value, ctx_traceback):
        self.close()
        if self.url.startswith("http") or self.url.startswith("https"):
            shutil.rmtree(self.target_dir)

    def clean(self):
        p = Popen(["git", "clean", "-fxd"], cwd=self.target_dir)
        return p.wait()

    def close(self):
        self.repo.close()

    def get_project_directory(self):
        return self.target_dir

    def get_project_name(self):
        return self.__get_project_name()

    def get_current_commit(self):
        return self.repo.head.object.hexsha

    def __get_project_name(self):
        url = self.url
        if self.url.endswith('.git'):
            url = self.url[:-4]

        project_name = self.url.split(os.path.sep)[-1]
        if project_name == "":
            return self.target_dir.split(os.path.sep)[-2]
        else:
            return project_name
    
    def archive(self, output):
        if not self.repo.bare:
            self.repo.archive(output)
        else:
            print("project doesn't contain any commits...")
            exit(1)

    def iterate_tagged_commits(self, max_commits=-1) -> Tag:
        git: Git = self.repo.git

        for i, tag in enumerate(reversed(self.repo.tags)):
            git.checkout(tag)
            yield self.get_current_commit()

            if max_commits == i:
                break
