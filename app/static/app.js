/**
 * FitForge Agent Client-side Interaction Logic (Milestone 1)
 */

async function loadSampleData() {
    const loadBtn = document.getElementById('load-sample-btn');
    const originalText = loadBtn.innerHTML;
    loadBtn.disabled = true;
    loadBtn.innerHTML = 'Loading sample...';

    try {
        const response = await fetch('/api/sample');
        if (!response.ok) {
            throw new Error(`Failed to fetch sample: ${response.statusText}`);
        }
        const sample = await response.json();

        document.getElementById('resume-text').value = sample.resume_text || '';
        document.getElementById('jd-text').value = sample.job_description_text || '';
        
        if (sample.priorities) {
            document.getElementById('min-comp').value = sample.priorities.min_compensation || '';
            document.getElementById('location-pref').value = sample.priorities.location_preference || '';
            document.getElementById('desired-role').value = sample.priorities.desired_role_type || '';
            document.getElementById('non-negotiables').value = (sample.priorities.non_negotiables || []).join('\n');
        }
    } catch (err) {
        console.error('Error loading sample data:', err);
        alert('Could not load sample data from server.');
    } finally {
        loadBtn.disabled = false;
        loadBtn.innerHTML = originalText;
    }
}

async function handleWorkflowSubmit(event) {
    event.preventDefault();

    const submitBtn = document.getElementById('submit-workflow-btn');
    const progressCard = document.getElementById('workflow-progress');
    const resultsContainer = document.getElementById('workflow-results-container');
    const stageText = document.getElementById('current-stage-text');

    const resumeText = document.getElementById('resume-text').value.trim();
    const jdText = document.getElementById('jd-text').value.trim();
    const minComp = document.getElementById('min-comp').value.trim();
    const locationPref = document.getElementById('location-pref').value.trim();
    const desiredRole = document.getElementById('desired-role').value.trim();
    const nonNegotiablesRaw = document.getElementById('non-negotiables').value.trim();

    if (!resumeText || !jdText) {
        alert('Please provide both Résumé Text and Job Description.');
        return;
    }

    const nonNegotiables = nonNegotiablesRaw
        ? nonNegotiablesRaw.split('\n').map(l => l.trim()).filter(l => l.length > 0)
        : [];

    const payload = {
        resume_text: resumeText,
        job_description_text: jdText,
        priorities: {
            min_compensation: minComp || null,
            location_preference: locationPref || null,
            desired_role_type: desiredRole || null,
            non_negotiables: nonNegotiables
        }
    };

    // UI state: running
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Processing Workflow...';
    progressCard.classList.remove('hidden');
    resultsContainer.innerHTML = '';

    const stages = [
        { id: 'step-intake', text: 'Intake Agent: Normalizing texts and checking completeness...' },
        { id: 'step-evidence', text: 'Evidence Agent: Extracting requirements and mapping evidence...' },
        { id: 'step-fit', text: 'Fit Analyst: Computing fit score and assessing alignment...' },
        { id: 'step-planner', text: 'Action Planner: Synthesizing strategy, brief, and interview talking points...' },
        { id: 'step-gate', text: 'Quality Gate: Auditing assertions and validating report integrity...' }
    ];

    // Animate stage indicators
    let stageIndex = 0;
    const interval = setInterval(() => {
        if (stageIndex < stages.length) {
            const current = stages[stageIndex];
            stageText.textContent = current.text;
            document.querySelectorAll('.step-node').forEach((node, idx) => {
                if (idx <= stageIndex) node.classList.add('active');
                if (idx < stageIndex) node.classList.add('completed');
            });
            stageIndex++;
        }
    }, 200);

    try {
        const response = await fetch('/api/workflows', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/html, application/json'
            },
            body: JSON.stringify(payload)
        });

        clearInterval(interval);

        // Mark all steps as complete
        document.querySelectorAll('.step-node').forEach(node => {
            node.classList.add('active', 'completed');
        });
        stageText.textContent = 'Workflow completed successfully!';

        if (!response.ok) {
            const errData = await response.json().catch(() => ({ detail: 'Workflow execution failed.' }));
            throw new Error(errData.detail || 'Server error during workflow execution.');
        }

        const htmlResult = await response.text();
        resultsContainer.innerHTML = htmlResult;
        resultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        clearInterval(interval);
        console.error('Workflow error:', err);
        resultsContainer.innerHTML = '';
        const alertBox = document.createElement('div');
        alertBox.className = 'alert-box alert-error';
        const alertIcon = document.createElement('div');
        alertIcon.className = 'alert-icon';
        alertIcon.textContent = '⚠️';
        const alertContent = document.createElement('div');
        const alertTitle = document.createElement('h4');
        alertTitle.textContent = 'Error Running Workflow';
        const alertMsg = document.createElement('p');
        alertMsg.textContent = err.message;
        alertContent.appendChild(alertTitle);
        alertContent.appendChild(alertMsg);
        alertBox.appendChild(alertIcon);
        alertBox.appendChild(alertContent);
        resultsContainer.appendChild(alertBox);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Run Agent Workflow
        `;
    }
}
