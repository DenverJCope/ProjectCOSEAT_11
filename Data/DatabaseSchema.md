# Database Schema Design

## 1. Overview

This document defines the initial relational database schema for the Traditional Knowledge Repository. The design translates the identified database requirements into entities, attributes and relationships that support repository content, cultural protocols, access conditions, tagging and human review.

The schema provides a straightforward initial structure for the current prototype requirements. Entities, attributes and relationships may be extended or revised as repository components and workflow requirements are further defined.



## 2. Schema Entities

### 2.1 Knowledge Items

The `knowledge_items` table represents the central content stored and managed by the repository.

| Attribute | Key | Description |
|---|---|---|
| `item_id` | Primary Key | Unique identifier for the knowledge item |
| `title` | | Title of the knowledge item |
| `content` | | Content or stored content reference |
| `content_type` | | Type or format of the content |
| `source` | | Source or provenance information |
| `cultural_category` | | Cultural classification associated with the item |
| `access_classification` | | Access category applied to the item |
| `consent_status` | | Current consent status |
| `review_status` | | Current quarantine or review state |
| `created_by` | Foreign Key | References the user who created or submitted the item |
| `created_at` | | Creation information |
| `updated_at` | | Most recent modification information |


### 2.2 Users

The `users` table represents individuals who interact with the repository and provides the basic user information required to support repository responsibilities and future access-control functionality.

| Attribute | Key | Description |
|---|---|---|
| `user_id` | Primary Key | Unique identifier for the user |
| `display_name` | | Name used to identify the user within the repository |
| `role` | | Repository role associated with the user |
| `account_status` | | Current status of the user account |
| `created_at` | | Creation information for the user record |
| `updated_at` | | Most recent modification information |


### 2.3 Tags

The `tags` table represents descriptive labels used to organise, classify and support the retrieval of knowledge items.

| Attribute | Key | Description |
|---|---|---|
| `tag_id` | Primary Key | Unique identifier for the tag |
| `tag_name` | | Name of the tag |
| `tag_description` | | Brief description of the tag |
| `tag_source` | | Indicates the origin of the tag, such as manual or AI-assisted |
| `review_status` | | Current review or approval state of the tag |
| `created_at` | | Creation information for the tag record |


### 2.4 Knowledge Item Tags

The `knowledge_item_tags` table connects knowledge items with their associated tags. It supports the many-to-many relationship between the two entities without duplicating tag information.

| Attribute | Key | Description |
|---|---|---|
| `item_id` | Primary Key, Foreign Key | References `knowledge_items.item_id` |
| `tag_id` | Primary Key, Foreign Key | References `tags.tag_id` |

The combination of `item_id` and `tag_id` forms a composite primary key, preventing the same tag from being associated with the same knowledge item more than once.

**Initial relationship:** One knowledge item may have multiple tags, and one tag may be associated with multiple knowledge items.


### 2.5 Cultural Protocols

The `cultural_protocols` table represents cultural handling and access conditions that may apply to repository knowledge. The database stores the relevant protocol information but does not independently determine culturally appropriate access or handling decisions.

| Attribute | Key | Description |
|---|---|---|
| `protocol_id` | Primary Key | Unique identifier for the cultural protocol |
| `protocol_name` | | Name used to identify the protocol |
| `protocol_description` | | Description of the protocol or guidance |
| `access_condition` | | Access condition associated with the protocol |
| `created_at` | | Creation information for the protocol record |
| `updated_at` | | Most recent modification information |


### 2.6 Knowledge Item Protocols

The `knowledge_item_protocols` table connects knowledge items with applicable cultural protocols. It supports the many-to-many relationship between knowledge items and protocols while keeping protocol information separately maintained.

| Attribute | Key | Description |
|---|---|---|
| `item_id` | Primary Key, Foreign Key | References `knowledge_items.item_id` |
| `protocol_id` | Primary Key, Foreign Key | References `cultural_protocols.protocol_id` |

The combination of `item_id` and `protocol_id` forms a composite primary key, preventing the same protocol from being associated with the same knowledge item more than once.

**Initial relationship:** One knowledge item may be associated with multiple cultural protocols, and one cultural protocol may apply to multiple knowledge items.



## 3. Entity Relationships

The initial database schema uses relationships between the core entities to avoid unnecessary duplication and maintain consistent references between repository information.


### 3.1 User to Knowledge Items

One user may create multiple knowledge items, while each knowledge item references one creating user.

**Relationship:** One-to-Many

`users.user_id` → `knowledge_items.created_by`


### 3.2 Knowledge Items to Tags

A knowledge item may have multiple tags, and a tag may be associated with multiple knowledge items. This many-to-many relationship is represented through the `knowledge_item_tags` junction table.

**Relationship:** Many-to-Many

`knowledge_items.item_id` → `knowledge_item_tags.item_id`

`tags.tag_id` → `knowledge_item_tags.tag_id`


### 3.3 Knowledge Items to Cultural Protocols

A knowledge item may be associated with multiple cultural protocols, and a cultural protocol may apply to multiple knowledge items. This many-to-many relationship is represented through the `knowledge_item_protocols` junction table.

**Relationship:** Many-to-Many

`knowledge_items.item_id` → `knowledge_item_protocols.item_id`

`cultural_protocols.protocol_id` → `knowledge_item_protocols.protocol_id`



## 4. Initial Design Scope

The initial schema intentionally focuses on the core information and relationships required by the current prototype. Review, consent and source information are represented using straightforward attributes within the existing entities where appropriate.

Additional entities or attributes may be introduced if later repository components require more detailed review histories, consent management, provenance records or access-control information. This allows the schema to evolve without introducing unnecessary complexity during the initial prototype stage.