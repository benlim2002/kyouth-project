# HomeFinder AI

## Project Overview

### Problem Statement

Purchasing a property is a complex decision involving multiple factors such as budget, location, property type, market activity, and affordability. Buyers often rely on scattered information and may struggle to compare different locations objectively.

### Target Users

* First-time home buyers
* Property investors
* Individuals searching for suitable residential areas in Malaysia

### System Goal

HomeFinder AI is a decision support system that helps users identify suitable property locations based on their preferences and constraints. The system combines structured property data with AI-generated reasoning to provide ranked recommendations.

---

# System Architecture

## Data Flow

```text
User Input
(Budget, State, Property Type)
            ↓
Property Database
(Filter Matching Properties)
            ↓
Ranking Engine
(Score Calculation)
            ↓
AI Reasoning Engine
(Explanation & Trade-off Analysis)
            ↓
Recommendation Dashboard
```

## Module Breakdown

### Data Processing Module

Responsible for:

* Cleaning property datasets
* Handling missing values
* Standardizing property attributes
* Generating location perks and insights

### Recommendation Engine

Responsible for:

* Filtering properties based on user constraints
* Calculating recommendation scores
* Ranking candidate locations

### AI Reasoning Module

Responsible for:

* Explaining recommendations
* Comparing alternatives
* Generating human-readable justifications

### Frontend Module

Responsible for:

* Collecting user preferences
* Displaying recommendations
* Showing ranking results
* Presenting AI-generated explanations

---

# Setup & Installation

## Prerequisites

* Docker
* Docker Compose

## Environment Variables

Create a `.env` file:

```env
BACKEND_URL=http://backend:8000/search
```

## Run Using Docker

```bash
docker compose up --build
```

## Access Application

Frontend:

```text
http://localhost:8000
```

Backend API:

```text
http://localhost:8080
```

---

# Features

## Property Preference Search

Users can specify:

* Budget
* Preferred state
* Property type

The system filters suitable properties from the database.

### Ranked Recommendations

The system evaluates multiple factors and ranks the top matching properties.

### AI-Powered Explanation

For each recommendation, the AI explains:

* Why the location is suitable
* Strengths of the recommendation
* Potential drawbacks

### Trade-off Analysis

Users can understand the differences between recommended locations, such as:

* Affordability
* Market activity
* Value per square foot
* Location perks

### Property Insights

Each recommendation includes:

* Median price
* Location highlights
* Recommendation score

---

# Technical Decisions

## Rule-Based Ranking + AI Explanation

Instead of allowing the language model to directly select properties, the system first filters and ranks properties using structured data.

The AI is then used to explain and justify the recommendations.

### Reasoning

This approach:

* Reduces hallucinations
* Ensures recommendations are grounded in real data
* Improves transparency

## Database-Driven Recommendations

Property information is stored in a structured database.

This allows:

* Fast filtering
* Consistent ranking
* Reproducible results

## Frontend and Backend Separation

The application follows a client-server architecture:

Frontend:

* User interface
* Recommendation display

Backend:

* Data processing
* Ranking logic
* AI integration

---

# Limitations

## Limited Dataset Coverage

Recommendations are limited to the available property dataset and may not reflect all properties currently available on the market.

## Simplified Ranking Logic

The scoring model currently considers only a subset of factors such as:

* Budget fit
* Property value
* Market activity

Other factors such as school accessibility, crime rates, and transportation networks are not included.

## Static Property Data

The system uses historical property statistics and does not include real-time property listings.

---

# Future Improvements

## Interactive Comparison Tool

Allow users to compare multiple townships side-by-side.

## Map Integration

Visualize recommended locations using interactive maps.

## Additional Property Factors

Include:

* Nearby public transport
* Schools
* Healthcare facilities
* Shopping centers

## Personalized Weighting

Allow users to prioritize factors such as:

* Lowest price
* Highest investment potential
* Best accessibility

## Real-Time Property Listings

Integrate with property listing platforms to provide live recommendations.
