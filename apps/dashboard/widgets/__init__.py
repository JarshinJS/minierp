class DashboardWidget:
    title = ""
    icon = ""
    allowed_roles = []

    def get_data(self, user):
        raise NotImplementedError
