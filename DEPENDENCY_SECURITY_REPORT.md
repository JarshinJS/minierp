# Dependency Security Report

## 1. Scope
Review of all dependencies defined in [requirements.txt](file:///d:/ODOO/Mini_ERP_System/requirements.txt) and currently installed in the virtual environment for known vulnerabilities, outdated releases, or unused packages.

---

## 2. Security Vulnerability Scan (CVEs)
A scan against the National Vulnerability Database (NVD) was performed for the core installed packages.

| Package Name | Installed Version | Latest Version | Known Vulnerabilities (CVEs) | Status |
|---|---|---|---|---|
| **Django** | `5.2.15` | `5.2.15` | None | **Secure** |
| **djangorestframework** | `3.15.2` | `3.17.1` | CVE-2024-21520 (Browsable API XSS) is **patched** in 3.15.2. | **Secure** |
| **celery** | `5.6.3` | `5.6.3` | None (CVE-2021-23727 resolved in >=5.2.2). | **Secure** |
| **redis** | `8.0.0` | `8.0.0` | None | **Secure** |
| **django-filter** | `24.3` | `25.2` | None | **Secure** |
| **django-htmx** | `1.27.0` | `1.27.0` | None | **Secure** |

---

## 3. Outdated Packages Analysis

The following packages are currently outdated:

1. **`djangorestframework`** (Installed: `3.15.2` | Latest: `3.17.1`):
   - *Risk*: Low. Current version includes all major security fixes.
   - *Recommendation*: Plan upgrade to `3.17.1` or later during the next maintenance window.
2. **`django-filter`** (Installed: `24.3` | Latest: `25.2`):
   - *Risk*: Low.
   - *Recommendation*: Upgrade to `25.2` to get performance improvements.
3. **`setuptools`** (Installed: `65.5.0` | Latest: `82.0.1`):
   - *Risk*: Low. Used only during setup/build.
   - *Recommendation*: Upgrade using `python -m pip install --upgrade setuptools`.

---

## 4. Unused Packages Analysis
All dependencies listed in `requirements.txt` are actively imported and used by the project applications (`apps/` and `core/`), or are used for testing (`pytest`, `factory_boy`, etc.). There are no unused packages.

---

## 5. Security Recommendations
1. **Regular Auditing**: Run `pip audit` or similar tools as part of the CI/CD pipeline to catch vulnerabilities before staging/production deployments.
2. **Pin Dependencies**: Keep dependencies pinned to minor/patch versions (as currently done in `requirements.txt`) to avoid breaking builds while ensuring reproducible deployments.
