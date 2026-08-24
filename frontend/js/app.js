/**
 * Smart Resume Screener - Frontend Application Logic
 * Integrates with FastAPI backend and flexible AI LLM provider (OpenRouter / OpenAI / Gemini)
 */

// API Configuration
const API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
  ? `${window.location.origin}/api/v1`
  : '/api/v1';

// Role & Description Presets
const PRESETS = {
  backend: {
    title: 'Senior Python & FastAPI Engineer',
    description: `We are seeking an experienced Senior Python Engineer to build scalable asynchronous microservices.

Core Responsibilities:
- Design, build, and maintain high-throughput backend APIs using FastAPI and Python 3.11+.
- Architect database schemas and optimize query performance using PostgreSQL, asyncpg, and SQLAlchemy 2.0.
- Containerize services with Docker and manage deployment configurations.
- Implement robust unit and integration testing pipelines.

Required Technical Skills:
- Python (FastAPI, AsyncIO, Pydantic)
- PostgreSQL & Database Indexing Optimization
- Docker & Containerization
- REST API Design, JWT Authentication & Security
- Git & CI/CD Pipelines

Nice to Have:
- Kubernetes, Redis Caching, RabbitMQ/Kafka, AWS Cloud Infrastructure.`
  },
  frontend: {
    title: 'Senior Frontend / React Architect',
    description: `Looking for a Senior Frontend Architect to lead development of our next-generation web application.

Requirements:
- 5+ years of extensive experience building enterprise SPAs with React, TypeScript, and Next.js.
- Strong proficiency in modern CSS (Flexbox, Grid, CSS Modules, animations, responsive design).
- State management with Zustand or Redux Toolkit.
- Web performance optimization, Core Web Vitals, and accessibility (a11y).
- Experience integrating complex REST and WebSocket APIs.`
  },
  ai: {
    title: 'AI / Machine Learning Engineer',
    description: `Seeking an Applied AI Engineer to design and deploy LLM-powered document intelligence pipelines.

Requirements:
- Strong Python programming and experience with NLP, PyTorch, and HuggingFace Transformers.
- Hands-on experience integrating LLM APIs (Gemini, OpenAI) with structured function calling and JSON output.
- Experience with Vector Databases (pgvector, ChromaDB, Qdrant) and Retrieval-Augmented Generation (RAG).
- Background in prompt engineering, evaluation metrics, and ATS or document parsing systems.`
  }
};

// Sample Resume Content for 1-Click Testing
const SAMPLE_RESUME_TEXT = `Alex Morgan
Email: alex.morgan@example.com | Phone: +1 (555) 432-8921
Location: San Francisco, CA | LinkedIn: linkedin.com/in/alexmorgan-dev

PROFESSIONAL SUMMARY
Senior Software Engineer with 6+ years of backend engineering expertise. Proven track record in architecting high-concurrency microservices with Python, FastAPI, and PostgreSQL. Passionate about distributed systems, API performance, and clean modular code.

TECHNICAL SKILLS
- Languages & Frameworks: Python, FastAPI, Django, AsyncIO, Pydantic, SQL, REST APIs, GraphQL
- Databases & Storage: PostgreSQL, Redis, MongoDB, SQLAlchemy 2.0, Alembic
- DevOps & Tools: Docker, Kubernetes, Git, GitHub Actions, AWS (EC2, S3, RDS), Linux, Nginx

WORK EXPERIENCE
Senior Backend Developer | TechFlow Cloud (2021 - Present)
- Architected and deployed 12+ asynchronous microservices using FastAPI, handling 15,000+ requests per second with sub-50ms latency.
- Led migration from monolithic architecture to PostgreSQL database with async connection pooling (asyncpg), improving query throughput by 42%.
- Integrated Docker and automated CI/CD pipelines deploying to AWS cloud environments.
- Implemented OAuth2 and JWT authentication mechanisms across enterprise client accounts.

Software Engineer | Apex Systems (2018 - 2021)
- Developed RESTful API endpoints in Python / Django for cloud document management.
- Designed database schemas, indexing strategies, and automated migrations.
- Mentored junior engineers and participated in architectural code reviews.

EDUCATION
Bachelor of Science in Computer Science
University of California, Berkeley (2014 - 2018)`;

// Application State
let currentScreeningResult = null;
let selectedFile = null;
let screeningHistory = [];

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initPresets();
  initDropzone();
  initFormSubmission();
  initActionButtons();
  loadHistoryFromStorage();
});

/* ==========================================================================
   1. NAVIGATION & TABS
   ========================================================================== */
function initNavigation() {
  const navButtons = document.querySelectorAll('.nav-btn[data-tab]');
  const tabContents = document.querySelectorAll('.tab-content');

  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTabId = btn.getAttribute('data-tab');

      navButtons.forEach(b => b.classList.remove('active'));
      tabContents.forEach(tc => tc.classList.remove('active'));

      btn.classList.add('active');
      const targetTab = document.getElementById(targetTabId);
      if (targetTab) targetTab.classList.add('active');

      if (targetTabId === 'pipeline-tab') {
        renderPipelineTable();
      }
    });
  });
}

/* ==========================================================================
   2. PRESETS MENU
   ========================================================================== */
function initPresets() {
  const presetToggleBtn = document.getElementById('preset-toggle-btn');
  const presetsMenu = document.getElementById('presets-menu');
  const jobTitleInput = document.getElementById('job-title');
  const jobDescTextarea = document.getElementById('job-description');
  const clearJdBtn = document.getElementById('clear-jd-btn');

  // Toggle Dropdown
  presetToggleBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    presetsMenu.classList.toggle('hidden');
  });

  // Close dropdown on click outside
  document.addEventListener('click', () => {
    presetsMenu.classList.add('hidden');
  });

  // Select Preset
  document.querySelectorAll('.preset-item').forEach(item => {
    item.addEventListener('click', () => {
      const presetKey = item.getAttribute('data-preset');
      const preset = PRESETS[presetKey];
      if (preset) {
        jobTitleInput.value = preset.title;
        jobDescTextarea.value = preset.description;
        showToast(`Loaded preset: ${preset.title}`);
      }
      presetsMenu.classList.add('hidden');
    });
  });

  // Clear Job Description
  clearJdBtn.addEventListener('click', () => {
    jobDescTextarea.value = '';
    jobDescTextarea.focus();
  });

  // Do NOT auto-populate fields on boot; the user should start with a clean form.
  // Preset values are loaded on demand via the 'Load Sample Role' dropdown.
}

/* ==========================================================================
   3. DRAG & DROP AND FILE HANDLING
   ========================================================================== */
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('resume-file');
  const selectedFileInfo = document.getElementById('selected-file-info');
  const fileNameDisplay = document.getElementById('file-name');
  const fileSizeDisplay = document.getElementById('file-size');
  const removeFileBtn = document.getElementById('remove-file-btn');
  const dropzoneContent = dropzone.querySelector('.dropzone-content');

  // Drag over styling
  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  // File Drop
  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelected(files[0]);
    }
  });

  // File Input Change
  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });

  // Remove File
  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileInput();
  });

  function handleFileSelected(file) {
    selectedFile = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = formatBytes(file.size);

    dropzoneContent.classList.add('hidden');
    selectedFileInfo.classList.remove('hidden');
  }

  function resetFileInput() {
    selectedFile = null;
    fileInput.value = '';
    dropzoneContent.classList.remove('hidden');
    selectedFileInfo.classList.add('hidden');
  }

  window.handleFileSelected = handleFileSelected;
  window.resetFileInput = resetFileInput;
}

/* ==========================================================================
   4. SAMPLE RESUME ATTACHMENT
   ========================================================================== */
function initSampleResumeButton() {
  const sampleBtn = document.getElementById('sample-resume-btn');
  sampleBtn.addEventListener('click', () => {
    const blob = new Blob([SAMPLE_RESUME_TEXT], { type: 'text/plain' });
    const file = new File([blob], 'alex_morgan_senior_backend_resume.txt', { type: 'text/plain' });
    
    document.getElementById('candidate-name').value = 'Alex Morgan';
    document.getElementById('candidate-email').value = 'alex.morgan@example.com';
    
    window.handleFileSelected(file);
    showToast('Loaded sample candidate resume (Alex Morgan)');
  });
}

/* ==========================================================================
   5. FORM SUBMISSION & SCREENING PIPELINE
   ========================================================================== */
function initFormSubmission() {
  const form = document.getElementById('screening-form');
  const submitBtn = document.getElementById('submit-screen-btn');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const jobTitle = document.getElementById('job-title').value.trim();
    const jobDescription = document.getElementById('job-description').value.trim();
    const candidateName = document.getElementById('candidate-name').value.trim() || 'Candidate';
    const candidateEmail = document.getElementById('candidate-email').value.trim();

    if (!jobDescription) {
      showToast('Please provide a job description.', 'error');
      return;
    }

    if (!selectedFile) {
      showToast('Please attach or drop a candidate resume file.', 'error');
      return;
    }

    // UI Loading State
    setScreeningState('loading');
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.7';

    // Build Multipart Form Data
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('job_description', jobDescription);
    formData.append('job_title', jobTitle);
    formData.append('full_name', candidateName);
    if (candidateEmail) formData.append('email', candidateEmail);

    // Progress Animation steps
    const stepInterval = animateLoadingSteps();

    try {
      const response = await fetch(`${API_BASE_URL}/screening/quick-screen`, {
        method: 'POST',
        body: formData,
      });

      clearInterval(stepInterval);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Screening evaluation failed' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const result = await response.json();
      currentScreeningResult = result;

      // Save to local pipeline history
      saveToPipelineHistory(result, candidateName, jobTitle);

      // Render Results Card
      renderScreeningResults(result, candidateName, jobTitle);
      setScreeningState('content');
      showToast('Screening evaluation completed successfully!', 'success');

    } catch (err) {
      clearInterval(stepInterval);
      console.error('Screening failed:', err);
      showToast(`Error: ${err.message}`, 'error');
      setScreeningState('empty');
    } finally {
      submitBtn.disabled = false;
      submitBtn.style.opacity = '1';
    }
  });
}

function animateLoadingSteps() {
  const steps = [
    { id: 'step-1', text: 'Extracting document text (pdfplumber/pypdf)...' },
    { id: 'step-2', text: 'Redacting contact PII (Name, Email, Phone) for bias-free screening...' },
    { id: 'step-3', text: 'Calling AI Evaluation API...' },
    { id: 'step-4', text: 'Synthesizing match ratings & justification...' },
  ];

  let currentStep = 0;
  const stepTextElem = document.getElementById('loading-step-text');

  // Reset steps
  document.querySelectorAll('.step-row').forEach(row => {
    row.classList.remove('active', 'completed');
  });
  document.getElementById(steps[0].id).classList.add('active');

  const interval = setInterval(() => {
    if (currentStep < steps.length - 1) {
      document.getElementById(steps[currentStep].id).classList.remove('active');
      document.getElementById(steps[currentStep].id).classList.add('completed');
      currentStep++;
      document.getElementById(steps[currentStep].id).classList.add('active');
      stepTextElem.textContent = steps[currentStep].text;
    }
  }, 1100);

  return interval;
}

/* ==========================================================================
   6. RENDER SCREENING RESULTS
   ========================================================================== */
function renderScreeningResults(data, candidateName, jobTitle) {
  // 1. Candidate Info & Decision Badge
  const initialsElem = document.getElementById('candidate-initials');
  const nameElem = document.getElementById('res-candidate-name');
  const titleElem = document.getElementById('res-job-title');
  const decisionBadge = document.getElementById('decision-badge');
  const decisionText = document.getElementById('decision-text');

  const displayName = candidateName || (data.resume?.candidate?.full_name) || 'Candidate';
  nameElem.textContent = displayName;
  titleElem.textContent = jobTitle || (data.job?.title) || 'Target Role';
  initialsElem.textContent = getInitials(displayName);

  // Normalize scores: overall_score can be 1-10 or 10-100 in database
  let overallScore = 7;
  if (data.detailed_feedback && data.detailed_feedback.overall_score_1_to_10) {
    overallScore = data.detailed_feedback.overall_score_1_to_10;
  } else if (data.match_score) {
    overallScore = data.match_score > 10 ? Math.round(data.match_score / 10) : Math.round(data.match_score);
  }
  overallScore = Math.min(Math.max(overallScore, 1), 10);

  const isShortlisted = overallScore >= 7;
  const isReview = overallScore >= 4 && overallScore < 7;

  if (isShortlisted) {
    decisionBadge.className = 'decision-pill status-shortlisted';
    decisionText.textContent = 'Shortlisted Candidate';
  } else if (isReview) {
    decisionBadge.className = 'decision-pill status-review';
    decisionText.textContent = 'Requires Review';
  } else {
    decisionBadge.className = 'decision-pill status-rejected';
    decisionText.textContent = 'Rejected';
  }

  // Update panel header status pill
  const panelPill = document.getElementById('panel-status-pill');
  if (panelPill) {
    const panelBadgeContainer = document.getElementById('result-status-badge');
    if (isShortlisted) {
      panelPill.className = 'status-pill status-shortlisted';
      panelPill.textContent = 'SHORTLISTED';
    } else if (isReview) {
      panelPill.className = 'status-pill status-review';
      panelPill.textContent = 'REQUIRES REVIEW';
    } else {
      panelPill.className = 'status-pill status-rejected';
      panelPill.textContent = 'REJECTED';
    }
    panelBadgeContainer.classList.remove('hidden');
  }

  // 2. Overall Radial Score
  const scoreOverallNum = document.getElementById('score-overall-num');
  const radialBar = document.getElementById('radial-progress-bar');
  const tierBadge = document.getElementById('score-tier-label');

  scoreOverallNum.textContent = overallScore;

  // Calculate circle dashoffset (Circumference is 263.89 for r=42)
  const circumference = 263.89;
  const offset = circumference - (circumference * (overallScore / 10));
  radialBar.style.strokeDashoffset = offset;

  if (overallScore >= 8) {
    radialBar.style.stroke = 'var(--emerald-green)';
    tierBadge.className = 'score-tier-badge tier-high';
    tierBadge.textContent = 'High Alignment';
  } else if (overallScore >= 6) {
    radialBar.style.stroke = 'var(--amber-gold)';
    tierBadge.className = 'score-tier-badge tier-medium';
    tierBadge.textContent = 'Moderate Alignment';
  } else {
    radialBar.style.stroke = 'var(--rose-red)';
    tierBadge.className = 'score-tier-badge tier-low';
    tierBadge.textContent = 'Low Alignment';
  }

  // 3. Sub-scores (Skills & Experience)
  let skillsScore = data.skills_match_score || (data.detailed_feedback?.skills_match_score_1_to_10) || overallScore;
  let expScore = data.experience_match_score || (data.detailed_feedback?.experience_match_score_1_to_10) || overallScore;
  
  skillsScore = Math.min(Math.max(Math.round(skillsScore), 1), 10);
  expScore = Math.min(Math.max(Math.round(expScore), 1), 10);

  document.getElementById('score-skills-val').textContent = `${skillsScore} / 10`;
  document.getElementById('progress-skills-bar').style.width = `${skillsScore * 10}%`;

  document.getElementById('score-exp-val').textContent = `${expScore} / 10`;
  document.getElementById('progress-exp-bar').style.width = `${expScore * 10}%`;

  // 4. Match Highlights: Render Matched & Missing Skills Badges
  renderSkillBadges(data.matched_skills, 'matched');
  renderSkillBadges(data.missing_skills, 'missing');

  // 5. Analysis Justification (render newlines as formatted paragraphs)
  const justificationText = data.analysis_summary || data.justification || data.detailed_feedback?.raw_justification || 'No justification provided.';
  const justElem = document.getElementById('res-justification-text');
  // Convert newlines to <br> and bullet markers to styled bullets
  const formatted = escapeHtml(justificationText)
    .replace(/\n\n+/g, '</p><p class="justification-paragraph">')
    .replace(/\n/g, '<br>')
    .replace(/^([-*•]\s+)/gm, '<span class="bullet-marker">&#8226;</span> ');
  justElem.innerHTML = formatted;
}

/**
 * Render green checkmark tags for matched skills and red warning tags for missing skills
 */
function renderSkillBadges(skillsList, type) {
  const containerId = type === 'matched' ? 'matched-skills-container' : 'missing-skills-container';
  const countBadgeId = type === 'matched' ? 'matched-count-badge' : 'missing-count-badge';
  const container = document.getElementById(containerId);
  const countBadge = document.getElementById(countBadgeId);

  container.innerHTML = '';
  const skills = Array.isArray(skillsList) ? skillsList : [];
  countBadge.textContent = skills.length;

  if (skills.length === 0) {
    const hint = document.createElement('span');
    hint.className = 'no-tags-hint';
    hint.textContent = type === 'matched' ? 'No direct skill matches detected.' : 'No major required skill gaps noted.';
    container.appendChild(hint);
    return;
  }

  skills.forEach(skill => {
    const badge = document.createElement('span');
    badge.className = `skill-badge ${type === 'matched' ? 'skill-badge-matched' : 'skill-badge-missing'}`;

    const iconSvg = type === 'matched'
      ? `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><polyline points="20 6 9 17 4 12"/></svg>`
      : `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;

    badge.innerHTML = `${iconSvg} <span>${escapeHtml(skill)}</span>`;
    container.appendChild(badge);
  });
}

/* ==========================================================================
   7. RESULTS STATE MANAGEMENT
   ========================================================================== */
function setScreeningState(state) {
  const emptyState = document.getElementById('results-empty');
  const loadingState = document.getElementById('results-loading');
  const contentState = document.getElementById('results-content');

  emptyState.classList.add('hidden');
  loadingState.classList.add('hidden');
  contentState.classList.add('hidden');

  if (state === 'empty') {
    emptyState.classList.remove('hidden');
  } else if (state === 'loading') {
    loadingState.classList.remove('hidden');
  } else if (state === 'content') {
    contentState.classList.remove('hidden');
  }
}

/* ==========================================================================
   8. ACTION BUTTONS & EXPORTS
   ========================================================================== */
function initActionButtons() {
  // Copy Justification Button
  const copyBtn = document.getElementById('copy-summary-btn');
  copyBtn.addEventListener('click', () => {
    const text = document.getElementById('res-justification-text').textContent;
    navigator.clipboard.writeText(text).then(() => {
      showToast('Justification copied to clipboard!');
    }).catch(() => {
      showToast('Failed to copy text', 'error');
    });
  });

  // Export JSON Report
  const downloadBtn = document.getElementById('download-json-btn');
  downloadBtn.addEventListener('click', () => {
    if (!currentScreeningResult) return;
    const jsonStr = JSON.stringify(currentScreeningResult, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screening_report_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Downloaded JSON screening report');
  });

  // Screen Another Resume
  const screenAnotherBtn = document.getElementById('screen-another-btn');
  screenAnotherBtn.addEventListener('click', () => {
    setScreeningState('empty');
    window.resetFileInput();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Refresh Pipeline Button
  const refreshPipelineBtn = document.getElementById('refresh-pipeline-btn');
  if (refreshPipelineBtn) {
    refreshPipelineBtn.addEventListener('click', () => {
      renderPipelineTable();
      showToast('Refreshed candidate pipeline');
    });
  }
}

/* ==========================================================================
   9. PIPELINE TABLE & LOCAL HISTORY
   ========================================================================== */
function saveToPipelineHistory(result, candidateName, jobTitle) {
  const overallScore = result.detailed_feedback?.overall_score_1_to_10 || (result.match_score > 10 ? Math.round(result.match_score / 10) : result.match_score) || 0;

  const statusStr = overallScore >= 7 ? 'SHORTLISTED' : overallScore >= 4 ? 'REQUIRES REVIEW' : 'REJECTED';
  const statusCls = overallScore >= 7 ? 'status-shortlisted' : overallScore >= 4 ? 'status-review' : 'status-rejected';

  const item = {
    id: result.id || Date.now(),
    candidateName: candidateName || 'Candidate',
    jobTitle: jobTitle || 'Target Role',
    overallScore,
    skillsScore: result.skills_match_score || 0,
    status: statusStr,
    statusCls,
    date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  };

  screeningHistory.unshift(item);
  if (screeningHistory.length > 20) screeningHistory.pop();
  try {
    localStorage.setItem('screening_history', JSON.stringify(screeningHistory));
  } catch (e) {}
}

function loadHistoryFromStorage() {
  try {
    const saved = localStorage.getItem('screening_history');
    if (saved) {
      screeningHistory = JSON.parse(saved);
    }
  } catch (e) {}
}

function renderPipelineTable() {
  const tbody = document.getElementById('pipeline-tbody');
  if (!tbody) return;

  if (screeningHistory.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="table-empty-cell">No candidates screened yet. Run an evaluation from the Screener tab.</td></tr>`;
    return;
  }

  tbody.innerHTML = '';
  screeningHistory.forEach(item => {
    const tr = document.createElement('tr');
    const scoreColor = item.overallScore >= 7 ? 'var(--emerald-green)' : item.overallScore >= 4 ? 'var(--amber-gold)' : 'var(--rose-red)';
    const pillCls = item.statusCls || (item.overallScore >= 7 ? 'status-shortlisted' : item.overallScore >= 4 ? 'status-review' : 'status-rejected');

    tr.innerHTML = `
      <td>
        <strong style="color: var(--text-primary); font-weight: 600;">${escapeHtml(item.candidateName)}</strong>
      </td>
      <td>${escapeHtml(item.jobTitle)}</td>
      <td>
        <span style="font-family: var(--font-mono); font-weight: 700; color: ${scoreColor};">
          ${item.overallScore} / 10
        </span>
      </td>
      <td>${item.skillsScore} / 10</td>
      <td>
        <span class="status-pill ${pillCls}" style="font-size: 0.72rem;">
          ${item.status}
        </span>
      </td>
      <td style="color: var(--text-muted); font-size: 0.78rem;">${item.date}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   10. UTILITIES (Toast, Formatting, Escaping)
   ========================================================================== */
function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'toast-error' : 'toast-success'}`;

  const iconSvg = type === 'error'
    ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`
    : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;

  toast.innerHTML = `${iconSvg} <span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getInitials(name) {
  if (!name) return 'CD';
  const parts = name.trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
