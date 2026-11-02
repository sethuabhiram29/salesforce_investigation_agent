"""Salesforce user fixture data for tests.

Contains predefined user records for:
- User with missing Federation ID (LOGIN-4 scenario)
- Deactivated delegated admin user (LOGIN-3A scenario)
- User with missing object permissions (OBJECT-1 / OBJECT-2 scenario)
- User with missing record and app permissions
- Healthy active mirror user with full permissions
"""

FIXTURE_USERS = [
    {
        "Id": "005xx000001LOGIN4",
        "Username": "jane.doe@acme.corp",
        "Email": "jane.doe@acme.corp",
        "FirstName": "Jane",
        "LastName": "Doe",
        "EmployeeNumber": "EMP-00104",
        "IsActive": True,
        "FederationIdentifier": None,  # LOGIN-4: missing FederationIdentifier
        "Profile": {
            "Id": "00exx0000000001",
            "Name": "Standard User"
        },
        "PermissionSets": ["CC360 Community User"],
        "UserPermissionsSupportUser": False,
        "DelegatedAdmin": False,
        "WizardCountry": "US",
    },
    {
        "Id": "005xx000002LOGIN3A",
        "Username": "john.smith@acme.corp",
        "Email": "john.smith@acme.corp",
        "FirstName": "John",
        "LastName": "Smith",
        "EmployeeNumber": "EMP-00103",
        "IsActive": False,  # LOGIN-3A: deactivated
        "FederationIdentifier": "EMP-00103",
        "Profile": {
            "Id": "00exx0000000002",
            "Name": "Delegated Administrator"
        },
        "PermissionSets": [],
        "UserPermissionsSupportUser": True,
        "DelegatedAdmin": True,
        "WizardCountry": "US",
    },
    {
        "Id": "005xx000003OBJECT1",
        "Username": "sarah.connor@acme.corp",
        "Email": "sarah.connor@acme.corp",
        "FirstName": "Sarah",
        "LastName": "Connor",
        "EmployeeNumber": "EMP-00102",
        "IsActive": True,
        "FederationIdentifier": "EMP-00102",
        "Profile": {
            "Id": "00exx0000000003",
            "Name": "Sales Representative"
        },
        "ObjectPermissions": {
            "Account": {"PermissionsRead": True, "PermissionsCreate": False, "PermissionsEdit": False, "PermissionsDelete": False},
            "Contact": {"PermissionsRead": True, "PermissionsCreate": True, "PermissionsEdit": True, "PermissionsDelete": False},
            "Opportunity": {"PermissionsRead": True, "PermissionsCreate": True, "PermissionsEdit": False, "PermissionsDelete": False},
        },
        "RecordAccess": {
            "006xx000001OPP": {"HasReadAccess": False, "HasEditAccess": False, "MaxAccessLevel": "None"},
            "001xx000001ACC": {"HasReadAccess": True, "HasEditAccess": False, "MaxAccessLevel": "Read"},
        },
        "PermissionSets": [],
        "DelegatedAdmin": False,
        "WizardCountry": None,  # OBJECT-1: Wizard country missing
    },
    {
        "Id": "005xx000004HEALTHY",
        "Username": "alex.taylor@acme.corp",
        "Email": "alex.taylor@acme.corp",
        "FirstName": "Alex",
        "LastName": "Taylor",
        "EmployeeNumber": "EMP-00101",
        "IsActive": True,
        "FederationIdentifier": "EMP-00101",
        "Profile": {
            "Id": "00exx0000000001",
            "Name": "Standard User"
        },
        "ObjectPermissions": {
            "Account": {"PermissionsRead": True, "PermissionsCreate": True, "PermissionsEdit": True, "PermissionsDelete": True},
            "Contact": {"PermissionsRead": True, "PermissionsCreate": True, "PermissionsEdit": True, "PermissionsDelete": True},
            "Opportunity": {"PermissionsRead": True, "PermissionsCreate": True, "PermissionsEdit": True, "PermissionsDelete": True},
        },
        "RecordAccess": {
            "006xx000001OPP": {"HasReadAccess": True, "HasEditAccess": True, "MaxAccessLevel": "All"},
            "001xx000001ACC": {"HasReadAccess": True, "HasEditAccess": True, "MaxAccessLevel": "All"},
        },
        "PermissionSets": ["CC360 Community User", "Cmty-PS Community User", "Conga_CLM_User"],
        "DelegatedAdmin": False,
        "WizardCountry": "US",
    },
    {
        "Id": "005xx000006LOGIN6",
        "Username": "daniel.ortiz@acme.corp",
        "Email": "daniel.ortiz@acme.corp",
        "FirstName": "Daniel",
        "LastName": "Ortiz",
        "EmployeeNumber": "EMP-20491",
        "IsActive": True,
        "FederationIdentifier": "EMP-10022",  # LOGIN-6: Mismatched Federation ID (old re-hire ID EMP-10022 vs active EMP-20491)
        "Profile": {
            "Id": "00exx0000000001",
            "Name": "Standard User"
        },
        "PermissionSets": ["CC360 Community User"],
        "DelegatedAdmin": False,
        "WizardCountry": "US",
    },
    {
        "Id": "005xx000007RANDOM",
        "Username": "corrupt.fed@acme.corp",
        "Email": "corrupt.fed@acme.corp",
        "FirstName": "Corrupt",
        "LastName": "Federation",
        "EmployeeNumber": "EMP-00105",
        "IsActive": True,
        "FederationIdentifier": "RANDOM_CORRUPT_XYZ_999",  # Random value that does not match EmployeeNumber
        "Profile": {
            "Id": "00exx0000000001",
            "Name": "Standard User"
        },
        "PermissionSets": [],
        "DelegatedAdmin": False,
        "WizardCountry": "US",
    }
]
