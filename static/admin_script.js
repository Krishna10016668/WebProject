/* static/admin_script.js */

// --- 1. Template Preview Logic ---
function toggleTemplate() {
    const preview = document.getElementById('templatePreview');
    if (preview) {
        preview.classList.toggle('hidden');
    }
}

// --- 2. Share Modal Logic ---
const shareModal = document.getElementById('shareModal');
const modalLinkInput = document.getElementById('modalLinkInput');
const modalEmailInput = document.getElementById('modalEmailInput');
const whatsappBtn = document.getElementById('whatsappBtn');

function openShareModal(link) {
    if (!shareModal || !modalLinkInput) return;

    modalLinkInput.value = link;
    if (modalEmailInput) modalEmailInput.value = ''; 
    
    // Update WhatsApp Link dynamically
    if (whatsappBtn) {
        const waText = encodeURIComponent(`Please fill out this survey: ${link}`);
        whatsappBtn.href = `https://wa.me/?text=${waText}`;
    }

    shareModal.classList.remove('hidden');
}

function closeShareModal() {
    if (shareModal) {
        shareModal.classList.add('hidden');
    }
}

// Copy link specifically from the modal "Copy Link" button
function copyFromModal() {
    if (modalLinkInput) {
        robustCopy(modalLinkInput.value);
    }
}

// Close modal if clicking outside the white box
window.onclick = function(event) {
    if (shareModal && event.target == shareModal) {
        closeShareModal();
    }
}

// --- 3. Copy To Clipboard Logic (Robust) ---
function robustCopy(text) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            alert(" Link copied to clipboard!");
        }).catch(() => {
            fallbackCopy(text);
        });
    } else {
        fallbackCopy(text);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed"; 
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    
    try {
        document.execCommand('copy');
        alert(" Link copied!");
    } catch (err) {
        prompt("Copy link manually:", text);
    }
    
    document.body.removeChild(ta);
}

// --- 4. Send Email Logic (AJAX) ---
function sendEmail() {
    const email = modalEmailInput.value;
    const link = modalLinkInput.value;
    
    // Find the send button inside the modal to toggle loading state
    const btn = document.querySelector('#shareModal button.bg-\\[\\#8e44ad\\]');

    if (!email) {
        alert("Please enter an email address");
        return;
    }

    const originalContent = btn ? btn.innerHTML : 'Send Now';
    if(btn) {
        btn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Sending...';
        btn.disabled = true;
    }

    fetch('/share_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, link: link })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(" Error: " + data.error);
        } else {
            alert(" " + (data.message || "Email sent successfully!"));
            closeShareModal();
        }
    })
    .catch(err => {
        console.error(err);
        alert(" Failed to connect to server.");
    })
    .finally(() => {
        if(btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    });
}

 document.addEventListener('DOMContentLoaded', () => {
            // Wait 2000 milliseconds (2 seconds)
            setTimeout(() => {
                // Select all elements with the class 'flash-msg'
                const alerts = document.querySelectorAll('.flash-msg');
                
                alerts.forEach(alert => {
                    // 1. Fade out effect
                    alert.style.transition = 'opacity 0.5s ease';
                    alert.style.opacity = '0';
                    
                    // 2. Remove from DOM after fade completes (0.5s later)
                    setTimeout(() => {
                        alert.remove();
                    }, 500);
                });
            }, 2000);
        });