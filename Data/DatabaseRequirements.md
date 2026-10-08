# Core Database Requirements

## 1. Purpose

The database will provide the core data layer for the Traditional Knowledge Repository by storing the information required to manage repository content, users, cultural protocols, access conditions and associated metadata. The database requirements are defined to support the repository's planned ingestion, review, access-control and retrieval functionality while maintaining traceability, human oversight and culturally appropriate handling of knowledge.



## 2. Core Data Entities

### 2.1 Knowledge Item

A knowledge item represents an individual piece of content managed by the repository. It is the central repository entity and must retain sufficient information to identify the content, describe its origin and classification, determine its current review state, and support appropriate access decisions. 

Required information may include:

- Unique item identifier
- Title and content or content reference
- Content type
- Source or provenance information
- Cultural category
- Access classification
- Consent status
- Review or quarantine status
- Creation and update information


### 2.2 User

A user represents an individual who interacts with the repository. User information must support identification, role-based responsibilities and appropriate access to repository content and functionality.

Required information may include:

- Unique user identifier
- Name or display name
- User role
- Access level or permissions
- Account status
- Creation and update information


### 2.3 Tag

A tag represents a descriptive label associated with repository content. Tags support the organisation, classification and retrieval of knowledge items and may later include tags proposed through AI-assisted functionality and confirmed through human review.

Required information may include:

- Unique tag identifier
- Tag name
- Tag description
- Tag source or origin
- Review or approval status
- Creation information


### 2.4 Cultural Protocol

A cultural protocol represents a rule, condition or guidance associated with the culturally appropriate handling and access of repository knowledge. Protocol information must support the repository's access-control and human-review processes without allowing automated functionality to override culturally governed decisions.

Required information may include:

- Unique protocol identifier
- Protocol name
- Protocol description
- Applicable cultural category
- Access conditions or restrictions
- Approval or review information
- Creation and update information



## 3. Supporting Information Requirements

In addition to the core entities, the repository must retain supporting information required to manage knowledge appropriately throughout its lifecycle. This information should support traceability, cultural governance, human review and subsequent repository functionality.

Supporting information requirements include:

- Source and provenance information for repository content
- Consent status associated with knowledge items
- Cultural and access classifications
- Quarantine and review status
- Human review and approval information
- Creation and modification information



## 4. Relationship Requirements

The database must support relationships between the identified information without unnecessarily duplicating data. Knowledge items may be associated with multiple tags and relevant cultural protocols, while users may perform authorised review or approval activities. These relationships must support subsequent repository functionality including ingestion, human review, access control, classification and retrieval.

The detailed relationship structure, including keys and cardinalities, will be defined during the database schema design stage.



## 5. Design Considerations

The database requirements are guided by the following considerations:

- Cultural protocols and access restrictions must remain enforceable throughout repository processes.
- Human oversight must be maintained for culturally sensitive review and approval decisions.
- Source and provenance information must remain traceable to the associated repository content.
- The data structure should support future repository components without unnecessary complexity.
- Development and testing should use synthetic or non-sensitive data rather than genuine culturally sensitive knowledge.
- The initial requirements may be refined as the prototype and stakeholder requirements develop.
