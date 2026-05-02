export const roles = [
  // {
  //   title: ["Full Stack", "Developer"],
  //   color: "#1a4ff5",
  //   stack: {
  //     primary:   ["React", "Node.js"],
  //     secondary: ["PostgreSQL", "REST APIs", "TypeScript", "Git"],
  //   },
  // },
  {
    title: ["Data", "Engineer"],
    color: "#0f6e56",
    stack: {
      primary:   ["Python", "ETL"],
      secondary: ["PostgreSQL", "SQL"],
    },
  },
  {
    title: ["Backend", "Developer"],
    color: "#7f77dd",
    stack: {
      primary:   ["Java", "Python"],
      secondary: ["Spring", "Docker", "REST APIs", "PostgreSQL"],
    },
  },
  {
    title: ["Python", "Developer"],
    color: "#ba7517",
    stack: {
      primary:   ["Python", "FastAPI", "FastAPI", "Django"],
      secondary: ["SQLAlchemy", "Supabase", "pytest"],
    },
  },
  {
    title: ["Java", "Developer"],
    color: "#a32d2d",
    stack: {
      primary:   ["Java", "Spring Boot"],
      secondary: ["Maven", "JUnit", "Hibernate", "REST APIs"],
    },
  },
]

export type Role = typeof roles[number]
