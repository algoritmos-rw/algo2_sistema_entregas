"""Clase AluRepo para manejar los repositorios individuales y grupales.
"""

import base64
import csv
import io
import os
import pathlib
import re
import tempfile

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Type, TypeVar

import git  # type: ignore
import github

from dotenv import load_dotenv
from git.objects.fun import traverse_tree_recursive  # type: ignore
from git.util import stream_copy  # type: ignore
from github import InputGitTreeElement
from github.GitTree import GitTree as GithubTree
from github.Repository import Repository as GithubRepo


load_dotenv()

T = TypeVar("T", bound="AluRepo")

ROOT_DIR = pathlib.Path(os.environ["CORRECTOR_ROOT"])
PLANILLA_TSV = ROOT_DIR / "conf" / "repos.tsv"

GITHUB_TOKEN = os.environ["CORRECTOR_GH_TOKEN"]


class AluRepo:
    """Clase para sincronizar un repo de alumne.
    """

    def __init__(self, repo_full: str, github_user: str):
        self.gh_repo: Optional[GithubRepo] = None  # TODO: Make this a @property.
        self.repo_full = repo_full
        self.github_user = github_user

    @classmethod
    def from_legajo(
        cls: Type[T], legajo: str, /, tp_id: str = None, *, force_column: str = None
    ) -> T:
        """Devuelve el AluRepo correspondiente a un legajo y entrega.

        Si se especifica una entrega con `tp_id`, se busca en la configuración
        qué columna de la planilla corresponde. Si no se indica entrega, el
        repositorio se busca en la columna DEFAULT_COLUMN, o `force_column` si
        se especifica.

        ==> Este método es el apropiado para entregas individuales, y funciona
            también para grupos, componiendo los legajos en una sola cadena,
            separados por caracter subrayado ("12345_123456", etc.).

        Raises:
          KeyError si no se encuentra el legajo
          ValueError si no hay repositorio configurado
        """
        if tp_id is not None and force_column is not None:
            raise ValueError("tp_id y force_column son incompatibles")

        column = cls.DEFAULT_COLUMN if force_column is None else force_column

        # TODO: mover esto a repos.yml
        if tp_id in {"abb", "hash", "heap", "tp2", "tp3"} or "_" in legajo:
            column = "Repo2"

        return cls.from_legajos(legajo.split("_"), column=column)

    @classmethod
    def from_grupo(cls: Type[T], group_id: List[str] = None) -> T:
        """Devuelve el objeto AluRepo correspondiente a un grupo.

        ==> Este es el mejor método para entregas grupales, si se sabe el nombre
            del grupo.

        Raises:
          KeyError si no se encuentra el legajo
          ValueError si no hay repositorio configurado, o no es único
        """
        legajos = []

        with open(PLANILLA_TSV, newline="") as fileobj:
            for row in csv.DictReader(fileobj, dialect="excel-tab"):
                if row["Grupo"] == group_id:
                    legajos.append(row["Legajo"])

        if not legajos:
            raise KeyError(f"no se encontró grupo {group_id} en la planilla")

        return cls.from_legajos(legajos, column="Repo2")

    @classmethod
    def from_legajos(cls: Type[T], legajos: List[str], /, *, column: str) -> T:
        """Función genérica para obtener un repositorio.

        Si no se especifica force_column, se usa DEFAULT_COLUMN. Si legajos
        tiene más de un elemento, pero los repositorios no coinciden, se lanza
        ValueError.

        Esta función no se debería usar directamente, y debería preferirsse una
        de las dos anteriores.
        """
        rows = []

        with open(PLANILLA_TSV, newline="") as fileobj:
            for row in csv.DictReader(fileobj, dialect="excel-tab"):
                if row["Legajo"] in legajos:
                    rows.append(row)

        if not rows:
            s = "s" if legajos[1:] else ""
            legajos_fmt = ", ".join(legajos)
            raise KeyError(f"no se encontró legajo{s} {legajos_fmt} en la planilla")

        repo_names = set()
        github_names = []

        for row in rows:
            if name := row[column]:
                repo_names.add(name)
            if ghuser := row["Github"]:
                github_names.append(ghuser)

        if not repo_names:
            raise ValueError(f"columna {column} vacía para {legajos}")
        elif len(repo_names) > 1:
            raise ValueError(f"múltiples repos posibles: {repo_names}")
        else:
            repo_full = repo_names.pop()

        return cls(repo_full, legajos, github_names)

    @property
    def url(self):
        return f"https://github.com/{self.repo_full}"

    def ensure_exists(self, *, skel_repo: str = None):
        """Crea el repositorio en Github, si no existe aún.

        Si el repositorio ya existe, no se hace nada. Si no existe, se lo
        crea y se le inicializa con los contenidos de `skel_repo`.

        Raises:
          github.GithubException si no se pudo crear el repositorio.
        """
        gh = github.Github(GITHUB_TOKEN)
        try:
            self.gh_repo = gh.get_repo(self.repo_full)
        except github.UnknownObjectException:
            pass
        else:
            return

        owner, name = self.repo_full.split("/", 1)
        organization = gh.get_organization(owner)

        # TODO: get all settings from repos.yml
        organization.create_repo(
            name,
            private=True,
            has_wiki=False,
            has_projects=False,
            has_downloads=False,
            allow_squash_merge=False,
            allow_rebase_merge=False,
        )

        # TODO: poner skel_repo en la configuración.
        if skel_repo is not None:
            skel_repo = f"git@github.com:{skel_repo}"
            repo_full = f"git@github.com:{self.repo_full}"
            with tempfile.TemporaryDirectory() as tmpdir:
                git.Repo.clone_from(skel_repo, tmpdir)
                git.cmd.Git(working_dir=tmpdir).push(
                    [repo_full, "refs/remotes/origin/*:refs/heads/*"]
                )

        # TODO: set up team access
        # TODO: configure branch protections

    def sync(self, entrega_dir: pathlib.Path, rama: str, *, target_subdir: str = None):
        """Importa una entrega a los repositorios de alumnes.

        Args:
          entrega_dir: ruta en repo externo con los archivos actualizados.
          rama: rama en la que actualizar la entrega.
          target_subdir: directorio que se debe actuaizar dentro el repositorio.
              Si no se especifica, se usa el nombre de la rama (usar la cadena
              vacía para actualizar el toplevel).

        Raises:
          github.UnknownObjectException si el repositorio no existe.
          github.GithubException si se recibió algún otro error de la API.
        """
        if target_subdir is None:
            target_subdir = rama

        gh = github.Github(GITHUB_TOKEN)
        repo = self.gh_repo or gh.get_repo(self.repo_full)
        gitref = repo.get_git_ref(f"heads/{rama}")
        ghuser = self.github_user
        prefix_re = re.compile(re.escape(target_subdir.rstrip("/") + "/"))

        # Estado actual del repo.
        cur_sha = gitref.object.sha
        # NOTE: como solo trabajamos en un subdirectorio, se podría limitar el uso
        # de recursive a ese directorio (si trabajáramos con repos muy grandes).
        cur_tree = repo.get_git_tree(cur_sha, recursive=True)
        cur_commit = repo.get_git_commit(cur_sha)

        # Tree de la entrega en master, para manejar borrados.
        baseref = repo.get_git_ref(f"heads/{repo.default_branch}")
        base_tree = repo.get_git_tree(baseref.object.sha, recursive=True)

        # Examinar el repo de entregas para obtener los commits a aplicar.
        entrega_repo = git.Repo(entrega_dir, search_parent_directories=True)
        entrega_relpath = entrega_dir.relative_to(entrega_repo.working_dir).as_posix()
        pending_commits = []
        cur_commit_date = cur_commit.author.date

        # La fecha de la API siempre viene en UTC, pero PyGithub no le asigna
        # timezone, y se interpretaría en zona horaria local por omisión. Ver
        # https://github.com/PyGithub/PyGithub/pull/704.
        cur_commit_date = cur_commit_date.replace(tzinfo=timezone.utc)

        for commit in entrega_repo.iter_commits(paths=[entrega_relpath]):
            if commit.authored_date > cur_commit_date.timestamp():
                pending_commits.append(commit)

        for commit in reversed(pending_commits):
            entrega_tree = commit.tree.join(entrega_relpath)
            tree_contents = tree_to_github(entrega_tree, target_subdir, repo)
            entrega_files = set(tree_contents.keys())
            tree_elements = list(tree_contents.values())
            tree_elements.extend(
                deleted_files(entrega_files, cur_tree, prefix_re, base_tree)
            )
            author_date = datetime.fromtimestamp(commit.authored_date).astimezone()
            author_info = github.InputGitAuthor(
                ghuser, f"{ghuser}@users.noreply.github.com", author_date.isoformat()
            )
            cur_tree = repo.create_git_tree(tree_elements, cur_tree)
            cur_commit = repo.create_git_commit(
                commit.message, cur_tree, [cur_commit], author_info
            )
            # Se necesita obtener el árbol de manera recursiva para tener
            # los contenidos del subdirectorio de la entrega.
            cur_tree = repo.get_git_tree(cur_tree.sha, recursive=True)

        gitref.edit(cur_commit.sha)


def tree_to_github(
    tree: git.Tree, target_subdir: str, gh_repo: GithubRepo
) -> Dict[str, InputGitTreeElement]:
    """Extrae los contenidos de un commit de Git en formato Tree de Github.

    Returns:
      un diccionario donde las claves son rutas en el repo, y los valores
      el InputGitTreeElement que los modifica.
    """
    odb = tree.repo.odb
    target_subdir = target_subdir.rstrip("/") + "/"
    entries = traverse_tree_recursive(odb, tree.binsha, target_subdir)
    contents = {}

    for sha, mode, path in entries:
        # TODO: get exclusion list from repos.yml
        if path.endswith("README.md"):
            continue
        fileobj = io.BytesIO()
        stream_copy(odb.stream(sha), fileobj)
        fileobj.seek(0)
        try:
            text = fileobj.read().decode("utf-8")
            input_elem = InputGitTreeElement(path, f"{mode:o}", "blob", text)
        except UnicodeDecodeError:
            # POST /trees solo permite texto, hay que crear un blob para binario.
            fileobj.seek(0)
            data = base64.b64encode(fileobj.read())
            blob = gh_repo.create_git_blob(data.decode("ascii"), "base64")
            input_elem = InputGitTreeElement(path, f"{mode:o}", "blob", sha=blob.sha)
        finally:
            contents[path] = input_elem

    return contents


def deleted_files(
    new_files: Set[str],
    cur_tree: GithubTree,
    match_re: re.Pattern = None,
    preserve_from: GithubTree = None,
) -> List[InputGitTreeElement]:
    """Calcula los archivos a borrar en el repositorio junto con la entrega.

    Dada una lista que representa los contenidos actuales de la nueva
    entrega, y dado el árbol existente, esta función calcula los archivos
    que deben ser borrados, y los devuelve en una lista. (Para borrar
    un archivo a través de la API de Github, lo que se necesita es un
    InputGitTreeElement con sha=None.)

    La expresión regular `match_re` se usa para filtrar los subdirectorios
    sobre los que procesar los borrados. Si se especifica `preserve_from`,
    nunca se borrarán archivos que estén presentes en ese árbol.
    """

    def filter_tree(t: GithubTree) -> Set[str]:
        return {
            e.path
            for e in t.tree
            if e.type == "blob" and (not match_re or match_re.match(e.path))
        }

    cur_files = filter_tree(cur_tree)
    preserve_files = filter_tree(preserve_from) if preserve_from else set()

    deletions = cur_files - new_files - preserve_files
    # mypy complains here because of https://github.com/PyGithub/PyGithub/issues/1707
    return [
        InputGitTreeElement(path, "100644", "blob", sha=None)  # type: ignore
        for path in deletions
    ]
