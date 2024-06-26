from functools import wraps
from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required
from app.models import Project, GitBranch, GitRepository, AnalyzeIssue,ProjectLog
from uuid import UUID
import json

blueprint = Blueprint('project',
                      __name__,
                      url_prefix='/project/<string:idproject>')


# Utility Functions
def get_project_from_id(idproject):
    project = Project.query.filter_by(project_id=idproject).first()
    if project:
        project.project_id = project.project_id.hex
    return project


def get_branches(idproject):
    try:
        # Assuming GitBranch is your SQLAlchemy model
        branches = GitBranch.query.filter_by(
            project_id=str(UUID(idproject))).all()
        return branches
    except Exception as e:
        # Log the exception or handle it as per your requirement
        print("An error occurred while fetching branches:", e)
        return None  # or any other appropriate action, such as raising the exception


# Decorators
def check_branch(func):

    @wraps(func)
    def decorated_function(*args, **kwargs):
        branchid = kwargs.get('branchid')
        if not branchid:
            return func(*args, **kwargs)

        branches = get_branches(kwargs.get('idproject'))
        branch_names = [branch.remote for branch in branches]
        if branchid not in branch_names:
            abort(404)
        return func(*args, **kwargs)

    return decorated_function


def marksdown(idproject, branch):
    try:
        file_path = (AnalyzeIssue.query.filter_by(project_id=str(
            UUID(idproject)),
                                                  branch=branch).first()).path_

        with open(file_path, encoding='utf-8') as user_file:
            filejson = user_file.read()

        stats = {
            'C': len(json.loads(filejson).get('critical', [])),
            'H': len(json.loads(filejson).get('high', [])),
            'M': len(json.loads(filejson).get('medium', [])),
            'L': len(json.loads(filejson).get('low', [])),
            'W': len(json.loads(filejson).get('weak', []))
        }

        return stats, json.loads(filejson)

    except Exception as e:
        print(f"Error: {e}")
        return {'C': 0, 'H': 0, 'M': 0, 'L': 0, 'W': 0}, {}


def check_idproject(func):

    @wraps(func)
    @login_required
    def decorated_function(*args, **kwargs):
        idproject = kwargs.get('idproject')
        project = get_project_from_id(idproject)
        if not project or project.username != current_user.username:
            abort(404)
        return func(*args, **kwargs)

    return decorated_function


# Routes
@blueprint.route("/", methods=["GET"])
@check_idproject
def index(idproject):
    project = get_project_from_id(idproject)
    return redirect(url_for('project.analysis', idproject=project.project_id))


@blueprint.route("/analysis", methods=["GET"])
@blueprint.route("/analysis/<string:branchid>", methods=["GET"])
@check_idproject
@check_branch
def analysis(idproject, branchid=None):
    project = get_project_from_id(idproject)
    branch_names = [branch.remote for branch in get_branches(idproject)]

    # Mendapatkan repository Git
    gitrepo = GitRepository.query.filter_by(
        project_id=str(UUID(idproject))).first()

    # Jika tidak ada branch yang ditentukan dan ada default branch, redirect ke default branch
    if project.analyze_status == "success":
        if branch_names is not None and branchid is None:
            if gitrepo.default_branch is not None:
                return redirect(
                    url_for('project.analysis',
                            idproject=project.project_id,
                            branchid=gitrepo.default_branch))

    stats, markdown_content = marksdown(idproject, branchid)

    filterContent = {
            'Severity': {"high","medium"},
            'Language': {"python","php"},
        }

    analysis_content = render_template(
        '/project_detail/analysis/branch.html',
        filterContent =filterContent
        ,
        content=markdown_content) if branchid else None
    title = f"Branch Dev - {project.project_name}" if branchid else f"Analysis - {project.project_name}"

    return render_template('/project_detail/analysis/index.html',
                           analysis_content=analysis_content,
                           BranchName=branchid,
                           stats=stats,
                           branches=branch_names,
                           title=title,
                           project=project)


@blueprint.route('/log', methods=["GET"])
@check_idproject
def log(idproject):
    project = get_project_from_id(idproject)
    log = ProjectLog.query.filter_by(project_id=idproject).all()
 
    return render_template(
        '/project_detail/log/log.html',
        title=f"log  - {project.project_name}",
        content = log,
        project=project,
    )


@blueprint.route('/log/<string:logid>')
@check_idproject
def log_by_id(idproject,logid):
    project = get_project_from_id(idproject)
    log = ProjectLog.query.filter_by(id=logid).first()

    try:
        with open(log.path_, 'r') as file:
            # Read the contents of the file and split into lines
            content = [line.rstrip('\n') for line in file]
    except FileNotFoundError:
        content = ""
    print(content)
    return render_template(
        '/project_detail/log/log_item.html',
        title=f"log details - {project.project_name}",
        project=project,
        content=log,
        logx=content
    )


@blueprint.route('/settings')
@check_idproject
def settings(idproject):
    project = get_project_from_id(idproject)
    return render_template(
        '/project_detail/settings/index.html',
        project=project,
    )


#api
