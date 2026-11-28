ROLE_PERMS = {
    "Admin":   "__all__",
    "Manager": ["add_project", "change_project", "delete_project",
                "add_task", "change_task", "delete_task", "view_project", "view_task"],
    "Member":  ["view_project", "view_task", "change_task"],
}