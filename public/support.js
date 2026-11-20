'use strict';
const supportForm = document.getElementById('support-form');
supportForm.addEventListener('submit', async event => {
  event.preventDefault();
  const button = supportForm.querySelector('button');
  const status = document.getElementById('support-status');
  const fields = Object.fromEntries(new FormData(supportForm));
  button.disabled = true;
  status.textContent = 'Saving your request…';
  try {
    const response = await fetch('/api/leads', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        submissionId: crypto.randomUUID(), name: fields.name, email: fields.email,
        company: '', venture: 'SimuTrade Labs', website: '',
        message: 'Support / ' + fields.topic + ': ' + fields.message,
        consent: supportForm.elements.consent.checked
      })
    });
    const result = await response.json();
    if (!response.ok || !result.reference) throw Error(result.error || 'The request was not confirmed. Please retry.');
    status.textContent = 'Your request is saved. Reference ' + result.reference + '. Keep this reference for follow-up.';
    supportForm.reset();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
