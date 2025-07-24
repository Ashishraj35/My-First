(() => {
  const authSection = document.getElementById('auth-section');
  const dashboardSection = document.getElementById('dashboard-section');
  const signupForm = document.getElementById('signup-form');
  const loginForm = document.getElementById('login-form');
  const uploadForm = document.getElementById('upload-form');
  const reportMonthInput = document.getElementById('report-month');
  const generateReportButton = document.getElementById('generate-report');
  const reportLinkContainer = document.getElementById('report-link');
  const logoutButton = document.getElementById('logout-button');
  let chart; // reference to the Chart.js instance

  // Helper to get token from localStorage
  function getToken() {
    return localStorage.getItem('token') || '';
  }

  // Show dashboard and load stats
  async function showDashboard() {
    authSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    await loadStats();
  }

  // Show auth forms and clear token
  function showAuthForms() {
    localStorage.removeItem('token');
    dashboardSection.classList.add('hidden');
    authSection.classList.remove('hidden');
  }

  // Load monthly spending data and render chart
  async function loadStats() {
    const token = getToken();
    if (!token) return;
    try {
      const resp = await fetch(`/api/stats?token=${encodeURIComponent(token)}`);
      if (!resp.ok) throw new Error('Failed to fetch stats');
      const data = await resp.json();
      const labels = Object.keys(data.stats);
      const values = Object.values(data.stats);
      const ctx = document.getElementById('statsChart').getContext('2d');
      if (chart) chart.destroy();
      chart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [
            {
              label: 'Monthly Expenditure',
              data: values,
              backgroundColor: 'rgba(0, 122, 204, 0.6)',
              borderColor: 'rgba(0, 122, 204, 1)',
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              title: {
                display: true,
                text: 'Amount',
              },
            },
            x: {
              title: {
                display: true,
                text: 'Month',
              },
            },
          },
        },
      });
    } catch (err) {
      console.error(err);
      alert('Error loading statistics');
    }
  }

  // Handle sign up
  signupForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = signupForm.username.value;
    const password = signupForm.password.value;
    const payload = { username, password };
    try {
      const resp = await fetch('/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const errData = await resp.json();
        alert(errData.detail || 'Failed to sign up');
        return;
      }
      const data = await resp.json();
      localStorage.setItem('token', data.token);
      signupForm.reset();
      loginForm.reset();
      await showDashboard();
    } catch (err) {
      console.error(err);
      alert('Error during sign up');
    }
  });

  // Handle login
  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = loginForm.username.value;
    const password = loginForm.password.value;
    const payload = { username, password };
    try {
      const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const errData = await resp.json();
        alert(errData.detail || 'Invalid credentials');
        return;
      }
      const data = await resp.json();
      localStorage.setItem('token', data.token);
      loginForm.reset();
      signupForm.reset();
      await showDashboard();
    } catch (err) {
      console.error(err);
      alert('Error during login');
    }
  });

  // Handle bill upload
  uploadForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const token = getToken();
    if (!token) {
      alert('Please log in');
      return;
    }
    const formData = new FormData(uploadForm);
    // Extract values
    const amount = parseFloat(formData.get('amount'));
    const bill_date = formData.get('bill_date');
    const bill_time = formData.get('bill_time');
    const shop = formData.get('shop');
    const file = uploadForm.file.files[0];
    if (!file) {
      alert('Please choose an image');
      return;
    }
    // Convert image to Base64
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result;
      const base64 = dataUrl.split(',')[1];
      const payload = {
        token: token,
        filename: file.name,
        image: base64,
        amount,
        bill_date,
        bill_time,
        shop,
      };
      try {
        const resp = await fetch('/api/upload_bill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!resp.ok) {
          const errData = await resp.json();
          alert(errData.detail || 'Failed to upload');
          return;
        }
        uploadForm.reset();
        await loadStats();
        alert('Bill uploaded successfully');
      } catch (err) {
        console.error(err);
        alert('Error uploading bill');
      }
    };
    reader.readAsDataURL(file);
  });

  // Handle report generation
  generateReportButton.addEventListener('click', async () => {
    const token = getToken();
    const month = reportMonthInput.value;
    reportLinkContainer.innerHTML = '';
    if (!month) {
      alert('Please select a month');
      return;
    }
    try {
      const resp = await fetch(`/api/monthly_report/${month}?token=${encodeURIComponent(token)}`);
      if (!resp.ok) {
        const errData = await resp.json();
        alert(errData.detail || 'Failed to generate report');
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report_${month}.pdf`;
      link.textContent = 'Download your PDF report';
      reportLinkContainer.appendChild(link);
    } catch (err) {
      console.error(err);
      alert('Error generating report');
    }
  });

  // Handle logout
  logoutButton.addEventListener('click', () => {
    showAuthForms();
  });

  // On page load, show dashboard if token exists
  window.addEventListener('load', async () => {
    const token = getToken();
    if (token) {
      await showDashboard();
    }
  });
})();
