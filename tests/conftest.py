import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pcs_project.settings')

def pytest_configure():
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', verbosity=0, interactive=False)
