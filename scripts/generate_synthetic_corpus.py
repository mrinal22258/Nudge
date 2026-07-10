import os
import json
import csv
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Define directories
CORPUS_DIR = Path("corpus")
RAW_DIR = CORPUS_DIR / "raw"
GT_DIR = CORPUS_DIR / "ground_truth"

RAW_DIR.mkdir(parents=True, exist_ok=True)
GT_DIR.mkdir(parents=True, exist_ok=True)

# Schema field definition helper
def make_resume(name, email, phone, links, education, experience, projects, skills, open_source):
    return {
        "name": name,
        "contact": {
            "email": email,
            "phone": phone,
            "links": links
        },
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "open_source_contributions": open_source
    }

# 15 synthetic resumes
resumes = {}

# 1. John Doe - Single-column, No traps
resumes["resume_1"] = (
    make_resume(
        name="John Doe",
        email="john.doe@example.com",
        phone="555-0100",
        links=["https://github.com/johndoe", "https://linkedin.com/in/johndoe"],
        education=[{
            "institution": "Stanford University",
            "degree": "Bachelor of Science",
            "field": "Computer Science",
            "start_date": "September 2018",
            "end_date": "June 2022",
            "gpa": 3.9
        }],
        experience=[{
            "company": "Tech Corp",
            "title": "Software Engineer",
            "start_date": "July 2022",
            "end_date": "Present",
            "bullets": [
                "Developed scalable microservices in Go and Python.",
                "Optimized database queries, reducing response latency by 30%.",
                "Led team of 3 developers to rebuild the legacy reporting system."
            ]
        }],
        projects=[{
            "name": "Task Scheduler",
            "description": "A lightweight distributed job scheduler written in Go.",
            "tech_stack": ["Go", "Redis", "Docker"],
            "links": ["https://github.com/johndoe/task-scheduler"]
        }],
        skills=["Go", "Python", "Docker", "Kubernetes", "Redis", "SQL"],
        open_source=[]
    ),
    "single-column",
    False
)

# 2. Jane Smith - Double-column, No traps
resumes["resume_2"] = (
    make_resume(
        name="Jane Smith",
        email="jane.smith@example.com",
        phone="555-0200",
        links=["https://github.com/janesmith"],
        education=[{
            "institution": "MIT",
            "degree": "Master of Science",
            "field": "Electrical Engineering",
            "start_date": "September 2019",
            "end_date": "June 2021",
            "gpa": 4.0
        }],
        experience=[{
            "company": "Robo Robotics",
            "title": "Robotics Developer",
            "start_date": "August 2021",
            "end_date": "Present",
            "bullets": [
                "Programmed control logic for autonomous vehicles using C++.",
                "Simulated robotic arms kinematic equations in ROS.",
                "Implemented real-time sensor fusion algorithms."
            ]
        }],
        projects=[{
            "name": "Lidar Filter",
            "description": "Point cloud preprocessing tool for LiDAR data.",
            "tech_stack": ["C++", "ROS", "PCL"],
            "links": ["https://github.com/janesmith/lidar-filter"]
        }],
        skills=["C++", "ROS", "Python", "Linux", "Robotics"],
        open_source=[]
    ),
    "double-column",
    False
)

# 3. Bob Vance - Single-column, Trap 1: Overlapping dates (consulting side-by-side with full-time)
resumes["resume_3"] = (
    make_resume(
        name="Bob Vance",
        email="bob.vance@example.com",
        phone="555-0300",
        links=["https://linkedin.com/in/bobvance"],
        education=[{
            "institution": "University of Pennsylvania",
            "degree": "Bachelor of Arts",
            "field": "Economics",
            "start_date": "September 2015",
            "end_date": "May 2019",
            "gpa": 3.6
        }],
        experience=[
            {
                "company": "Blue Widgets Inc",
                "title": "Financial Analyst",
                "start_date": "June 2019",
                "end_date": "Present",
                "bullets": [
                    "Created quarterly financial models and projections.",
                    "Analyzed operational costs and suggested efficiency gains."
                ]
            },
            {
                "company": "Scranton Consulting",
                "title": "Independent Consultant",
                "start_date": "January 2021",
                "end_date": "Present",
                "bullets": [
                    "Provided financial consulting to small local retail businesses.",
                    "Streamlined inventory tracking workflows."
                ]
            }
        ],
        projects=[],
        skills=["Excel", "Financial Modeling", "Consulting", "SQL"],
        open_source=[]
    ),
    "single-column",
    True  # Trap 1: Overlapping dates (June 2019 - Present vs Jan 2021 - Present)
)

# 4. Charlie Brown - Table-based, Trap 2: Project listed under projects AND experience bullets
resumes["resume_4"] = (
    make_resume(
        name="Charlie Brown",
        email="charlie.brown@example.com",
        phone="555-0400",
        links=["https://github.com/charliebrown"],
        education=[{
            "institution": "UC Berkeley",
            "degree": "BS",
            "field": "Computer Science",
            "start_date": "September 2016",
            "end_date": "May 2020",
            "gpa": 3.7
        }],
        experience=[{
            "company": "Search Corp",
            "title": "Software Engineer Intern",
            "start_date": "June 2019",
            "end_date": "August 2019",
            "bullets": [
                "Designed and built the 'Kite-Tracker' tool, an analytics dashboard for weather balloon trajectories, which became a core company project.",
                "Wrote clean, tested React and TypeScript code."
            ]
        }],
        projects=[{
            "name": "Kite-Tracker",
            "description": "An analytics dashboard for tracking and mapping weather balloon trajectories.",
            "tech_stack": ["React", "TypeScript", "Node.js"],
            "links": ["https://github.com/charliebrown/kite-tracker"]
        }],
        skills=["React", "TypeScript", "Node.js", "Python"],
        open_source=[]
    ),
    "table-based",
    True  # Trap 2: Kite-Tracker listed as project and mentioned in experience
)

# 5. Diana Prince - Double-column, Trap 3: Embedded Github link inside experience bullets prose
resumes["resume_5"] = (
    make_resume(
        name="Diana Prince",
        email="diana.prince@example.com",
        phone="555-0500",
        links=["https://github.com/dianaprince", "https://linkedin.com/in/dianaprince"],
        education=[{
            "institution": "Oxford University",
            "degree": "Doctor of Philosophy",
            "field": "Archaeology",
            "start_date": "October 2010",
            "end_date": "June 2014",
            "gpa": 3.95
        }],
        experience=[{
            "company": "National Museum",
            "title": "Lead Researcher",
            "start_date": "September 2014",
            "end_date": "Present",
            "bullets": [
                "Led team in digitizing historical artifacts. Catalog is available online at my github repository https://github.com/dianaprince/museum-digital-catalog.",
                "Published 12 research papers on antiquity archiving."
            ]
        }],
        projects=[],
        skills=["Archiving", "Research", "SQL", "Python"],
        open_source=[]
    ),
    "double-column",
    True  # Trap 3: GitHub link https://github.com/dianaprince/museum-digital-catalog embedded in experience bullets prose
)

# 6. Evan Wright - Single-column, Traps 1 & 2 (Overlapping dates & cross-listed project)
resumes["resume_6"] = (
    make_resume(
        name="Evan Wright",
        email="evan.wright@example.com",
        phone="555-0600",
        links=["https://github.com/evanwright"],
        education=[{
            "institution": "University of Michigan",
            "degree": "BS",
            "field": "Software Engineering",
            "start_date": "September 2017",
            "end_date": "May 2021",
            "gpa": 3.8
        }],
        experience=[
            {
                "company": "App Builders Inc",
                "title": "Junior Developer",
                "start_date": "June 2021",
                "end_date": "Present",
                "bullets": [
                    "Maintained client web applications.",
                    "Collaborated on 'Fast-Cache' middleware optimization."
                ]
            },
            {
                "company": "Freelance Contracting",
                "title": "Full Stack Contractor",
                "start_date": "December 2022",
                "end_date": "Present",
                "bullets": [
                    "Engineered the 'Fast-Cache' middleware library for high-throughput node applications, serving 1M requests daily.",
                    "Built responsive React dashboards for various clients."
                ]
            }
        ],
        projects=[{
            "name": "Fast-Cache",
            "description": "High-throughput Redis-backed Node caching middleware.",
            "tech_stack": ["Node.js", "Redis", "TypeScript"],
            "links": ["https://github.com/evanwright/fast-cache"]
        }],
        skills=["Node.js", "Redis", "React", "TypeScript"],
        open_source=[]
    ),
    "single-column",
    True  # Traps 1 & 2
)

# 7. Fiona Gallagher - Double-column, Traps 2 & 3 (Cross-listed project & embedded GitHub link in project description)
resumes["resume_7"] = (
    make_resume(
        name="Fiona Gallagher",
        email="fiona.g@example.com",
        phone="555-0700",
        links=["https://linkedin.com/in/fionag"],
        education=[{
            "institution": "City College of Chicago",
            "degree": "Associate Degree",
            "field": "Business Administration",
            "start_date": "September 2012",
            "end_date": "June 2014",
            "gpa": 3.4
        }],
        experience=[{
            "company": "Patsys Pies",
            "title": "Manager",
            "start_date": "July 2014",
            "end_date": "October 2018",
            "bullets": [
                "Managed inventory, staff scheduling, and daily sales logs.",
                "Implemented 'Pie-Tracker' Excel automated sheets to optimize kitchen prep times."
            ]
        }],
        projects=[{
            "name": "Pie-Tracker",
            "description": "An Excel automation macro project. Source code is published at https://github.com/fionag/pie-tracker for community auditing.",
            "tech_stack": ["VBA", "Excel"],
            "links": ["https://github.com/fionag/pie-tracker"]
        }],
        skills=["Management", "Excel", "Accounting"],
        open_source=[]
    ),
    "double-column",
    True  # Traps 2 & 3
)

# 8. George Costanza - Table-based, Traps 1 & 3 (Overlapping dates & embedded github link in contacts prose)
resumes["resume_8"] = (
    make_resume(
        name="George Costanza",
        email="george.c@example.com",
        phone="555-0800",
        links=["https://github.com/gcostanza/importer"],
        education=[{
            "institution": "Queens College",
            "degree": "BA",
            "field": "General Studies",
            "start_date": "September 1982",
            "end_date": "May 1986",
            "gpa": 2.5
        }],
        experience=[
            {
                "company": "New York Yankees",
                "title": "Assistant to the Traveling Secretary",
                "start_date": "March 1994",
                "end_date": "May 1997",
                "bullets": [
                    "Managed hotel bookings and charter flights.",
                    "Improved travel logistics system. Reach me at my github page https://github.com/gcostanza/importer for code samples."
                ]
            },
            {
                "company": "Play Now",
                "title": "Sales Representative",
                "start_date": "June 1997",
                "end_date": "September 1997",
                "bullets": [
                    "Handled corporate accounts for playground equipment.",
                    "Managed overlap transitions during Yankees departure."
                ]
            }
        ],
        projects=[],
        skills=["Logistics", "Negotiation", "Travel Booking"],
        open_source=[]
    ),
    "table-based",
    True  # Traps 1 & 3
)

# 9. Harry Potter - Single-column, All Three Traps
resumes["resume_9"] = (
    make_resume(
        name="Harry Potter",
        email="harry.potter@example.com",
        phone="555-0900",
        links=["https://github.com/hpotter/wand-builder"],
        education=[{
            "institution": "Hogwarts School",
            "degree": "N.E.W.T.",
            "field": "Defense Against the Dark Arts",
            "start_date": "September 1991",
            "end_date": "June 1998",
            "gpa": 3.8
        }],
        experience=[
            {
                "company": "Ministry of Magic",
                "title": "Auror",
                "start_date": "July 1998",
                "end_date": "Present",
                "bullets": [
                    "Investigated dark magic threats.",
                    "Created the 'Wand-Builder' simulation tool for training recruits."
                ]
            },
            {
                "company": "Hogwarts School",
                "title": "Guest Instructor",
                "start_date": "September 2002",
                "end_date": "June 2005",
                "bullets": [
                    "Taught practical defense techniques to OWL students.",
                    "Shared simulations from my project code repo https://github.com/hpotter/wand-builder for student use."
                ]
            }
        ],
        projects=[{
            "name": "Wand-Builder",
            "description": "Simulation software for testing wand core properties under various conditions. Code is hosted at https://github.com/hpotter/wand-builder.",
            "tech_stack": ["Python", "Tkinter"],
            "links": ["https://github.com/hpotter/wand-builder"]
        }],
        skills=["Defense", "Leadership", "Teaching"],
        open_source=[]
    ),
    "single-column",
    True  # All three traps
)

# 10. Iris West - Double-column, No Traps
resumes["resume_10"] = (
    make_resume(
        name="Iris West",
        email="iris.west@example.com",
        phone="555-1000",
        links=["https://linkedin.com/in/iriswest"],
        education=[{
            "institution": "Central City University",
            "degree": "BA",
            "field": "Journalism",
            "start_date": "September 2011",
            "end_date": "June 2015",
            "gpa": 3.7
        }],
        experience=[{
            "company": "Central City Picture News",
            "title": "Investigative Reporter",
            "start_date": "July 2015",
            "end_date": "Present",
            "bullets": [
                "Conducted interviews and wrote front-page articles on city incidents.",
                "Managed the digital newsroom archive transition."
            ]
        }],
        projects=[],
        skills=["Writing", "Editing", "SEO", "Research"],
        open_source=[]
    ),
    "double-column",
    False
)

# 11. Kevin Malone - Single-column, No Traps
resumes["resume_11"] = (
    make_resume(
        name="Kevin Malone",
        email="kevin.malone@example.com",
        phone="555-1100",
        links=["https://linkedin.com/in/kevinmalone"],
        education=[{
            "institution": "Penn State University",
            "degree": "BS",
            "field": "Accounting",
            "start_date": "September 1988",
            "end_date": "May 1992",
            "gpa": 2.8
        }],
        experience=[{
            "company": "Dunder Mifflin",
            "title": "Accountant",
            "start_date": "June 1992",
            "end_date": "Present",
            "bullets": [
                "Balanced branch ledgers and processed invoice reports.",
                "Implemented 'Keleven' mathematics logic to correct minor account gaps."
            ]
        }],
        projects=[],
        skills=["Ledger Management", "Excel", "Data Entry"],
        open_source=[]
    ),
    "single-column",
    False
)

# 12. Lois Lane - Single-column, Trap 1: Overlapping education and experience dates
resumes["resume_12"] = (
    make_resume(
        name="Lois Lane",
        email="lois.lane@example.com",
        phone="555-1200",
        links=["https://linkedin.com/in/loislane"],
        education=[{
            "institution": "Metropolis University",
            "degree": "Bachelor of Arts",
            "field": "Journalism",
            "start_date": "September 2005",
            "end_date": "May 2009",
            "gpa": 3.9
        }],
        experience=[
            {
                "company": "Daily Planet",
                "title": "Junior Reporter",
                "start_date": "September 2008",
                "end_date": "Present",
                "bullets": [
                    "Wrote local interest columns while completing senior university year.",
                    "Covered high-profile city alerts."
                ]
            }
        ],
        projects=[],
        skills=["Reporting", "Breaking News", "Editing"],
        open_source=[]
    ),
    "single-column",
    True  # Trap 1: Overlapping education (Sep 2005 - May 2009) and experience (Sep 2008 - Present)
)

# 13. Michael Scott - Table-based, Trap 2: Project listed under experience and projects
resumes["resume_13"] = (
    make_resume(
        name="Michael Scott",
        email="michael.scott@example.com",
        phone="555-1300",
        links=["https://linkedin.com/in/michaelscott"],
        education=[{
            "institution": "Scranton High School",
            "degree": "Diploma",
            "field": "General",
            "start_date": "September 1980",
            "end_date": "June 1984",
            "gpa": 3.0
        }],
        experience=[{
            "company": "Dunder Mifflin",
            "title": "Regional Manager",
            "start_date": "May 2001",
            "end_date": "Present",
            "bullets": [
                "Managed branch operations and drove local paper sales.",
                "Produced 'Threat-Level-Midnight', an interactive training video project."
            ]
        }],
        projects=[{
            "name": "Threat-Level-Midnight",
            "description": "Interactive branch safety and sales training video production.",
            "tech_stack": ["Video Production", "Screenwriting"],
            "links": ["https://linkedin.com/in/michaelscott/threat-level-midnight"]
        }],
        skills=["Management", "Sales", "Inspiration"],
        open_source=[]
    ),
    "table-based",
    True  # Trap 2
)

# 14. Nancy Drew - Double-column, Trap 3: Github link embedded in skills/contributions prose
resumes["resume_14"] = (
    make_resume(
        name="Nancy Drew",
        email="nancy.drew@example.com",
        phone="555-1400",
        links=["https://linkedin.com/in/nancydrew"],
        education=[{
            "institution": "River Heights College",
            "degree": "BA",
            "field": "Criminology",
            "start_date": "September 2016",
            "end_date": "June 2019",
            "gpa": 3.9
        }],
        experience=[{
            "company": "Drew Detective Agency",
            "title": "Private Investigator",
            "start_date": "July 2019",
            "end_date": "Present",
            "bullets": [
                "Solved local theft and mystery cases.",
                "Developed open-source tooling for case metadata aggregation."
            ]
        }],
        projects=[],
        skills=["Observation", "Logic", "Python"],
        open_source=[{
            "repo": "Case-Tracker",
            "pr_link": "https://github.com/nancydrew/case-tracker",
            "description": "Contributed case logging utilities. Pull request is active at https://github.com/nancydrew/case-tracker/pull/4 for validation."
        }]
    ),
    "double-column",
    True  # Trap 3: GitHub PR link embedded in open-source PR description
)

# 15. Oscar Martinez - Single-column, Traps 1 & 2 (Overlapping dates & cross-listed project)
resumes["resume_15"] = (
    make_resume(
        name="Oscar Martinez",
        email="oscar.m@example.com",
        phone="555-1500",
        links=["https://github.com/omartinez", "https://linkedin.com/in/oscarmartinez"],
        education=[{
            "institution": "Penn State University",
            "degree": "MBA",
            "field": "Finance",
            "start_date": "September 1993",
            "end_date": "June 1995",
            "gpa": 3.85
        }],
        experience=[
            {
                "company": "Dunder Mifflin",
                "title": "Senior Accountant",
                "start_date": "August 1995",
                "end_date": "Present",
                "bullets": [
                    "Audited branch cash balances and managed internal ledgers.",
                    "Designed 'Ledger-Audit', an automated tool for transaction verification."
                ]
            },
            {
                "company": "Scranton Coalition",
                "title": "Treasurer",
                "start_date": "January 2005",
                "end_date": "Present",
                "bullets": [
                    "Managed financial reporting and local tax declarations.",
                    "Applied Ledger-Audit tools for coalition balances."
                ]
            }
        ],
        projects=[{
            "name": "Ledger-Audit",
            "description": "Automated ledger checking scripts in Python.",
            "tech_stack": ["Python", "Pandas"],
            "links": ["https://github.com/omartinez/ledger-audit"]
        }],
        skills=["Accounting", "Python", "Pandas", "Auditing"],
        open_source=[]
    ),
    "single-column",
    True  # Traps 1 & 2
)


# Function to generate PDF using ReportLab
def generate_pdf(filename, data, layout_type):
    doc = SimpleDocTemplate(str(filename), pagesize=letter,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom colors
    primary_color = colors.HexColor("#1A365D")  # Dark blue
    text_color = colors.HexColor("#2D3748")     # Charcoal
    
    # Custom styles
    styles.add(ParagraphStyle(
        name='ResumeTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=primary_color,
        spaceAfter=6
    ))
    
    styles.add(ParagraphStyle(
        name='ResumeSubTitle',
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=text_color,
        spaceAfter=15
    ))
    
    styles.add(ParagraphStyle(
        name='SectionHeading',
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    ))
    
    styles.add(ParagraphStyle(
        name='JobHeader',
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=text_color,
        spaceBefore=4,
        spaceAfter=2,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name='BulletText',
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=text_color
    ))

    story = []
    
    # Header block
    story.append(Paragraph(data["name"], styles['ResumeTitle']))
    contact_str = f"Email: {data['contact']['email']} | Phone: {data['contact']['phone']}"
    if data['contact']['links']:
        contact_str += " | " + " | ".join(data['contact']['links'])
    story.append(Paragraph(contact_str, styles['ResumeSubTitle']))
    
    # Single-column and table-based rendering
    if layout_type == "single-column" or layout_type == "table-based":
        # 1. Experience
        if data["experience"]:
            story.append(Paragraph("WORK EXPERIENCE", styles['SectionHeading']))
            for exp in data["experience"]:
                header_p = Paragraph(f"<b>{exp['company']}</b> — {exp['title']} ({exp['start_date']} - {exp['end_date']})", styles['JobHeader'])
                story.append(header_p)
                bullets_list = []
                for b in exp["bullets"]:
                    bullets_list.append(ListItem(Paragraph(b, styles['BulletText']), leftIndent=15, bulletOffsetY=-2))
                story.append(ListFlowable(bullets_list, bulletType='bullet', start='circle', bulletFontName='Helvetica', bulletFontSize=5, spaceAfter=8))
                
        # 2. Education
        if data["education"]:
            story.append(Paragraph("EDUCATION", styles['SectionHeading']))
            for edu in data["education"]:
                edu_str = f"<b>{edu['institution']}</b> — {edu['degree']} in {edu['field']} ({edu['start_date']} - {edu['end_date']})"
                if edu.get("gpa"):
                    edu_str += f" | GPA: {edu['gpa']}"
                story.append(Paragraph(edu_str, styles['BulletText']))
                story.append(Spacer(1, 4))
                
        # 3. Projects
        if data["projects"]:
            story.append(Paragraph("PROJECTS", styles['SectionHeading']))
            for proj in data["projects"]:
                proj_header = f"<b>{proj['name']}</b>"
                if proj.get("tech_stack"):
                    proj_header += f" (Tech: {', '.join(proj['tech_stack'])})"
                story.append(Paragraph(proj_header, styles['JobHeader']))
                story.append(Paragraph(proj['description'], styles['BulletText']))
                if proj.get("links"):
                    story.append(Paragraph(f"Links: {', '.join(proj['links'])}", styles['BulletText']))
                story.append(Spacer(1, 6))
                
        # 4. Skills
        if data["skills"]:
            story.append(Paragraph("SKILLS", styles['SectionHeading']))
            story.append(Paragraph(", ".join(data["skills"]), styles['BulletText']))
            
        # 5. Open Source
        if data["open_source_contributions"]:
            story.append(Paragraph("OPEN SOURCE CONTRIBUTIONS", styles['SectionHeading']))
            for osc in data["open_source_contributions"]:
                story.append(Paragraph(f"<b>{osc['repo']}</b> (PR: {osc['pr_link']})", styles['JobHeader']))
                story.append(Paragraph(osc['description'], styles['BulletText']))
                story.append(Spacer(1, 4))

    elif layout_type == "double-column":
        # Render as a two-column table to fit typical two-column layouts
        left_flowables = []
        right_flowables = []
        
        # Left column (Contacts & Skills & Education)
        left_flowables.append(Paragraph("CONTACT INFO", styles['SectionHeading']))
        left_flowables.append(Paragraph(f"Email: {data['contact']['email']}", styles['BulletText']))
        left_flowables.append(Paragraph(f"Phone: {data['contact']['phone']}", styles['BulletText']))
        for link in data['contact']['links']:
            left_flowables.append(Paragraph(link, styles['BulletText']))
            
        if data["skills"]:
            left_flowables.append(Paragraph("SKILLS", styles['SectionHeading']))
            left_flowables.append(Paragraph(", ".join(data["skills"]), styles['BulletText']))
            
        if data["education"]:
            left_flowables.append(Paragraph("EDUCATION", styles['SectionHeading']))
            for edu in data["education"]:
                left_flowables.append(Paragraph(f"<b>{edu['institution']}</b>", styles['JobHeader']))
                left_flowables.append(Paragraph(f"{edu['degree']} in {edu['field']}", styles['BulletText']))
                left_flowables.append(Paragraph(f"{edu['start_date']} - {edu['end_date']}", styles['BulletText']))
                if edu.get("gpa"):
                    left_flowables.append(Paragraph(f"GPA: {edu['gpa']}", styles['BulletText']))
                left_flowables.append(Spacer(1, 6))

        # Right column (Work & Projects & Open Source)
        if data["experience"]:
            right_flowables.append(Paragraph("WORK EXPERIENCE", styles['SectionHeading']))
            for exp in data["experience"]:
                right_flowables.append(Paragraph(f"<b>{exp['company']}</b> — {exp['title']}", styles['JobHeader']))
                right_flowables.append(Paragraph(f"<i>{exp['start_date']} - {exp['end_date']}</i>", styles['BulletText']))
                bullets_list = []
                for b in exp["bullets"]:
                    bullets_list.append(ListItem(Paragraph(b, styles['BulletText']), leftIndent=12, bulletOffsetY=-2))
                right_flowables.append(ListFlowable(bullets_list, bulletType='bullet', spaceAfter=8))
                
        if data["projects"]:
            right_flowables.append(Paragraph("PROJECTS", styles['SectionHeading']))
            for proj in data["projects"]:
                proj_header = f"<b>{proj['name']}</b>"
                right_flowables.append(Paragraph(proj_header, styles['JobHeader']))
                right_flowables.append(Paragraph(proj['description'], styles['BulletText']))
                if proj.get("links"):
                    right_flowables.append(Paragraph(f"Links: {', '.join(proj['links'])}", styles['BulletText']))
                right_flowables.append(Spacer(1, 6))
                
        if data["open_source_contributions"]:
            right_flowables.append(Paragraph("OPEN SOURCE CONTRIBUTIONS", styles['SectionHeading']))
            for osc in data["open_source_contributions"]:
                right_flowables.append(Paragraph(f"<b>{osc['repo']}</b>", styles['JobHeader']))
                right_flowables.append(Paragraph(osc['description'], styles['BulletText']))
                right_flowables.append(Paragraph(f"PR: {osc['pr_link']}", styles['BulletText']))
                right_flowables.append(Spacer(1, 4))
                
        # Setup columns table
        col_table = Table([[left_flowables, right_flowables]], colWidths=[200, 310])
        col_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (0,0), 0),
            ('RIGHTPADDING', (0,0), (0,0), 10),
            ('LEFTPADDING', (1,0), (1,0), 10),
            ('RIGHTPADDING', (1,0), (1,0), 0),
        ]))
        story.append(col_table)
        
    doc.build(story)

# Populate the files
manifest_data = []

for name, (data, layout_type, has_traps) in resumes.items():
    pdf_filename = RAW_DIR / f"{name}.pdf"
    json_filename = GT_DIR / f"{name}.json"
    
    # 1. Save JSON Ground Truth
    with open(json_filename, "w") as f:
        json.dump(data, f, indent=2)
        
    # 2. Render PDF
    generate_pdf(pdf_filename, data, layout_type)
    
    # 3. Add to manifest
    manifest_data.append({
        "filename": f"{name}.pdf",
        "source": "synthetic",
        "layout_type": layout_type,
        "has_traps": str(has_traps)
    })
    print(f"Generated {name} ({layout_type}) successfully.")

# Write manifest.csv
with open(CORPUS_DIR / "manifest.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["filename", "source", "layout_type", "has_traps"])
    writer.writeheader()
    writer.writerows(manifest_data)

print("Corpus generation complete.")
