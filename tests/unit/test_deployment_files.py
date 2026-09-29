import re
from pathlib import Path
from unittest import TestCase

ROOT = Path(__file__).resolve().parents[2]


def read(name):
    return (ROOT / name).read_text()


class DeploymentFilesTest(TestCase):
    def test_gunicorn_is_a_runtime_dependency(self):
        main_dependencies = read("pyproject.toml").split("[tool.poetry.dependencies]")[1].split("[tool.poetry.group")[0]
        self.assertIn("gunicorn", main_dependencies)

    def test_dockerfile_serves_the_app_with_gunicorn_on_the_port_of_the_host(self):
        dockerfile = read("Dockerfile")
        self.assertRegex(dockerfile, r"gunicorn .*codex\.main:codex")
        self.assertIn("${PORT", dockerfile)

    def test_dockerfile_builds_the_database_when_the_image_is_built(self):
        self.assertIn("python -m codex.data.local_data_loader", read("Dockerfile"))

    def test_dockerfile_installs_the_package_from_the_source_tree(self):
        # the bundled data is found relative to the source, so the package must not be copied elsewhere
        self.assertRegex(read("Dockerfile"), r"pip install .*-e \.")

    def test_dockerignore_keeps_the_neuroglancer_files_and_local_data_out_of_the_image(self):
        ignored = read(".dockerignore").split()
        for path in ["data/l1_skeletons", "data/l1_meshes", "static/data", ".git"]:
            self.assertIn(path, ignored)
        self.assertNotIn("data/l1_export", ignored)

    def test_render_blueprint_generates_the_secret_key_and_uses_the_free_plan(self):
        blueprint = read("render.yaml")
        self.assertRegex(blueprint, r"key: FLASK_SECRET_KEY\s+generateValue: true")
        self.assertIn("plan: free", blueprint)
        self.assertIn("runtime: docker", blueprint)
        self.assertRegex(blueprint, r"key: CODEX_DATA_REF\s+value: main")

    def test_readme_explains_the_deployment(self):
        readme = read("README.md")
        self.assertIn("Deployment", readme)
        self.assertIn("FLASK_SECRET_KEY", readme)
