"""
eval_data/dataset.py
====================
Synthetic evaluation dataset — 25 resumes with known ground truth.
NO real personal information is used.
"""

from __future__ import annotations

DATASET: list[dict] = [
    {
        "id": "R01_senior_engineer",
        "notes": "Standard well-structured resume; all fields present",
        "text": """Alice Johnson
alice.johnson@techcorp.com | +1 (650) 555-0101 | Palo Alto, CA
https://linkedin.com/in/alicejohnson | https://github.com/alicejohnson

SUMMARY
Senior Software Engineer, 6 years in distributed systems.

EDUCATION
M.Sc. Computer Science — Stanford University, 2018
B.Sc. Computer Engineering — UC Berkeley, 2016

TECHNICAL SKILLS
Python, Go, Rust, Java, JavaScript

TOOLS & PLATFORMS
Kubernetes, Docker, AWS, GCP, Terraform, Kafka

EXPERIENCE
Senior Software Engineer — DistribCo (Mar 2020 – Present)
  • Led migration from monolith to microservices, reducing latency by 40%.
  • Managed a team of 5 engineers.

Software Engineer — StartupX (Jun 2018 – Feb 2020)
  • Built REST APIs serving 500K daily users.

PROJECTS
OpenTrace — Distributed tracing library (Go, gRPC, Prometheus)
DataPipe — Real-time ETL framework (Python, Kafka, Postgres)

CERTIFICATIONS
Google Cloud Professional Data Engineer (2022)
AWS Certified Solutions Architect Associate (2021)
""",
        "expected": {
            "full_name": "Alice Johnson",
            "email": "alice.johnson@techcorp.com",
            "phone": "+1 (650) 555-0101",
            "location": "Palo Alto, CA",
            "education_count": 2,
            "graduation_years": ["2018", "2016"],
            "has_technical_skills": True,
            "work_experience_count": 2,
            "project_count": 2,
            "certification_count": 2,
            "linkedin_url_present": True,
            "github_url_present": True,
        },
    },
    {
        "id": "R02_indian_developer",
        "notes": "Indian format phone, single degree, single job",
        "text": """Ravi Kumar
ravi.kumar@example.in | +91-99887-76655 | Bengaluru, India
linkedin.com/in/ravikumar99

EDUCATION
B.Tech Computer Science — IIT Madras, 2020

SKILLS
Java, Spring Boot, Python, MySQL, Redis, Docker

EXPERIENCE
Software Developer — Infosys Ltd (Aug 2020 – Present)
  • Developed REST APIs for banking clients.
  • Improved query performance by 30%.

PROJECTS
PayGateway — Payment processing microservice (Java, Spring Boot, MySQL)
""",
        "expected": {
            "full_name": "Ravi Kumar",
            "email": "ravi.kumar@example.in",
            "phone": "+91-99887-76655",
            "location": "Bengaluru, India",
            "education_count": 1,
            "graduation_years": ["2020"],
            "has_technical_skills": True,
            "work_experience_count": 1,
            "project_count": 1,
            "certification_count": 0,
            "linkedin_url_present": True,
            "github_url_present": False,
        },
    },
    {
        "id": "R03_ml_researcher",
        "notes": "PhD, publications, research roles, portfolio URL",
        "text": """Dr. Elena Rostova
elena.rostova@ai-research.org | +44 20 7946 0958 | London, UK
https://linkedin.com/in/elenarostova | https://github.com/erostova | https://erostova.dev

SUMMARY
Research Scientist specialising in generative models and RLHF.

EDUCATION
Ph.D. Computer Science — University of Cambridge, 2021
M.Phil. Machine Learning — University of Cambridge, 2017
B.Sc. Mathematics & CS — University of Edinburgh, 2016

SKILLS & TOOLS
Python, PyTorch, JAX, CUDA, HuggingFace, Ray, Weights & Biases

EXPERIENCE
Research Scientist — DeepMind (Oct 2021 – Present)
  • Developed alignment algorithms for LLMs.
  • Published 4 papers at NeurIPS and ICML.

Postdoctoral Fellow — Cambridge AI Lab (Jan 2021 – Sep 2021)
  • Investigated representation learning in vision transformers.

PROJECTS
AlignLLM — Open-source alignment toolbox (Python, PyTorch)
RL-Gym-Plus — Extended RL environments (Python, JAX)

CERTIFICATIONS
Deep Learning Specialization — Coursera (2018)
""",
        "expected": {
            "full_name": "Elena Rostova",
            "email": "elena.rostova@ai-research.org",
            "phone": "+44 20 7946 0958",
            "location": "London, UK",
            "education_count": 3,
            "graduation_years": ["2021", "2017", "2016"],
            "has_technical_skills": True,
            "work_experience_count": 2,
            "project_count": 2,
            "certification_count": 1,
            "linkedin_url_present": True,
            "github_url_present": True,
            "portfolio_url_present": True,
        },
    },
    {
        "id": "R04_fresh_grad",
        "notes": "No work experience, multiple academic projects, internship only",
        "text": """Priya Sharma
priya.sharma2024@gmail.com | 9876543210 | Mumbai, Maharashtra
https://github.com/priyasharma2024

EDUCATION
B.E. Information Technology — VJTI Mumbai, 2024

PROGRAMMING LANGUAGES
C++, Java, Python, JavaScript, SQL

FRAMEWORKS & TOOLS
React.js, Node.js, Express, MongoDB, Git

INTERNSHIP
Web Development Intern — CodeCraft Technologies (Jun 2023 – Aug 2023)
  • Built customer dashboard using React and Node.js.
  • Implemented JWT authentication and responsive UI.

ACADEMIC PROJECTS
SmartCampus — Campus facility booking portal (React, Node.js, MongoDB)
AlgoVisualizer — Interactive algorithm visualizer tool (JavaScript, HTML5 Canvas)
BookStoreAPI — RESTful API for online bookstore (Java, Spring Boot, MySQL)
""",
        "expected": {
            "full_name": "Priya Sharma",
            "email": "priya.sharma2024@gmail.com",
            "phone": "9876543210",
            "location": "Mumbai, Maharashtra",
            "education_count": 1,
            "graduation_years": ["2024"],
            "has_technical_skills": True,
            "work_experience_count": 1,
            "project_count": 3,
            "certification_count": 0,
            "linkedin_url_present": False,
            "github_url_present": True,
        },
    },
    {
        "id": "R05_career_changer",
        "notes": "Transition from mechanical engineering to full stack developer",
        "text": """Carlos Mendez
carlos.mendez.dev@gmail.com | (555) 234-5678 | Austin, TX
https://linkedin.com/in/carlos-mendez-dev | https://carlosmendez.tech

PROFESSIONAL SUMMARY
Mechanical Engineer turned Full Stack Developer. Experience in IoT and dashboard development.

TECHNICAL SKILLS
JavaScript, TypeScript, Python, React, Next.js, FastAPI, PostgreSQL, Docker, MQTT

EDUCATION
Certificate in Full Stack Web Development — UT Austin Bootcamp, 2023
B.S. Mechanical Engineering — Texas A&M University, 2019

EXPERIENCE
Junior Software Developer — IoT Solutions Inc. (Nov 2023 – Present)
  • Engineered telemetry visualization dashboard with React and WebSockets.
  • Integrated automated telemetry alerts with PostgreSQL backend.

Mechanical Design Engineer — Apex Manufacturing (Jul 2019 – Aug 2023)
  • Designed automated manufacturing fixtures and robotic test rigs.
  • Led CAD prototyping and supplier quality audits.

PROJECTS
EnergyTracker — Home IoT energy monitoring dashboard (Next.js, FastAPI, InfluxDB)
FleetMap — Real-time vehicle telematics simulator (TypeScript, React, Leaflet)
""",
        "expected": {
            "full_name": "Carlos Mendez",
            "email": "carlos.mendez.dev@gmail.com",
            "phone": "(555) 234-5678",
            "location": "Austin, TX",
            "education_count": 2,
            "graduation_years": ["2023", "2019"],
            "has_technical_skills": True,
            "work_experience_count": 2,
            "project_count": 2,
            "certification_count": 0,
            "linkedin_url_present": True,
            "github_url_present": False,
            "portfolio_url_present": True,
        },
    },
]
