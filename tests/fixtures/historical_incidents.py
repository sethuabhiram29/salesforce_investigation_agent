"""Historical incident fixture data for tests and offline demonstrations.

Contains predefined historical records with confirmed root causes and resolutions across all domains.
"""

FIXTURE_HISTORICAL_INCIDENTS = [
    # --- LOGIN DOMAIN PRECEDENTS ---
    {
        "incident_id": "INC0100101",
        "summary": "User account deactivated after extended leave",
        "description": "User cannot login to Salesforce. User record shows inactive status set by system policy.",
        "domain": "Login",
        "root_cause": "LOGIN-3: User account got deactivated",
        "resolution": "Re-activated user record (User.IsActive = True) after identity verification.",
        "similarity": 0.92,
    },
    {
        "incident_id": "INC0091823",
        "summary": "User getting SAML SSO error when signing into Salesforce",
        "description": "User Jane Doe is unable to log in via Okta SSO. Error states user not found in identity assertion. FederationIdentifier is blank.",
        "domain": "Login",
        "root_cause": "LOGIN-4: User Federation ID not available",
        "resolution": "Updated User.FederationIdentifier to match SSO employee identifier and verified login.",
        "similarity": 0.88,
    },
    {
        "incident_id": "INC0100103",
        "summary": "User Account not found in Salesforce org",
        "description": "New employee cannot access Salesforce. Search in user table returns 0 matching records.",
        "domain": "Login",
        "root_cause": "LOGIN-1: User Account not available",
        "resolution": "Provisioned new Salesforce user license and assigned base profile.",
        "similarity": 0.75,
    },
    {
        "incident_id": "INC0100105",
        "summary": "User Federation ID suspended in identity provider",
        "description": "User SSO fails with suspended assertion error in Okta.",
        "domain": "Login",
        "root_cause": "LOGIN-5: User Federation ID suspended",
        "resolution": "Re-enabled identity federation token in identity provider.",
        "similarity": 0.70,
    },
    # --- OBJECT DOMAIN PRECEDENTS ---
    {
        "incident_id": "INC0073210",
        "summary": "Cannot edit Account records",
        "description": "User reports Insufficient Privileges error when attempting to edit Account billing address. Peer with same role can edit.",
        "domain": "Object",
        "root_cause": "OBJECT-1: Missing Edit permission on Account object in assigned Permission Set",
        "resolution": "Assigned Account-Standard-Edit permission set to user.",
        "similarity": 0.89,
    },
    {
        "incident_id": "INC0073211",
        "summary": "Sales representative lacks edit permission compared to peer",
        "description": "User lacks edit permission on Account records. Working fine for peer with same sales profile.",
        "domain": "Object",
        "root_cause": "OBJECT-2: Object edit permission discrepancy vs mirror user",
        "resolution": "Aligned permission sets with mirror user baseline.",
        "similarity": 0.85,
    },
    # --- RECORD DOMAIN PRECEDENTS ---
    {
        "incident_id": "INC0062145",
        "summary": "Insufficient privileges on Opportunity record",
        "description": "User cannot open specific Opportunity record. User receives insufficient privileges error due to row-level sharing.",
        "domain": "Record",
        "root_cause": "RECORD-3: Row-level Opportunity access blocked by sharing rule",
        "resolution": "Added user to sharing rule public group for row-level access.",
        "similarity": 0.91,
    },
    # --- APPLICATION DOMAIN PRECEDENTS ---
    {
        "incident_id": "INC0051289",
        "summary": "Unable to access CC360 Customer Portal",
        "description": "User cannot see CC360 navigation tab or portal. Peer has full CC360 access.",
        "domain": "Application",
        "root_cause": "APPLICATION-1: CC360 Community Portal Access Missing",
        "resolution": "Assigned Customer Care 360 permission set license.",
        "similarity": 0.90,
    },
]
