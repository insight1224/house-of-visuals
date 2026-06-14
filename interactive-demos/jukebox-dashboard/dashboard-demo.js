const initialEvents = [
  {
    name: "Juneteenth Celebration",
    date: "2026-06-20",
    tickets: 86,
    revenue: 1720,
    status: "Upcoming"
  },
  {
    name: "Quiet Storm Live",
    date: "2026-07-18",
    tickets: 64,
    revenue: 1280,
    status: "Upcoming"
  },
  {
    name: "Battle of the DJs: Summer Edition",
    date: "2026-08-22",
    tickets: 98,
    revenue: 2940,
    status: "Upcoming"
  },
  {
    name: "Spring R&B Social",
    date: "2026-04-11",
    tickets: 112,
    revenue: 2800,
    status: "Completed"
  }
];

let demoEvents = structuredClone(initialEvents);
let currentAction = "";
let currentTourStep = 0;
let toastTimer;

const pageTitle = document.getElementById("pageTitle");
const navItems = document.querySelectorAll(".nav-item");
const dashboardViews = document.querySelectorAll(".dashboard-view");
const sidebar = document.getElementById("demoSidebar");
const mobileMenuButton = document.getElementById("mobileMenuButton");

const welcomeModal = document.getElementById("welcomeModal");
const actionModal = document.getElementById("actionModal");
const actionModalTitle = document.getElementById("actionModalTitle");
const actionModalText = document.getElementById("actionModalText");
const demoActionForm = document.getElementById("demoActionForm");
const demoActionInput = document.getElementById("demoActionInput");

const eventsTableBody = document.getElementById("eventsTableBody");
const eventSearch = document.getElementById("eventSearch");
const eventStatusFilter = document.getElementById("eventStatusFilter");

const tourOverlay = document.getElementById("tourOverlay");
const tourStepLabel = document.getElementById("tourStepLabel");
const tourTitle = document.getElementById("tourTitle");
const tourDescription = document.getElementById("tourDescription");
const tourBackButton = document.getElementById("tourBackButton");
const tourNextButton = document.getElementById("tourNextButton");

const demoToast = document.getElementById("demoToast");

const actionContent = {
  "create-event": {
    title: "Create a Sample Event",
    text: "Add a temporary sample event to see how a new event can appear inside the dashboard.",
    placeholder: "Example: Friday Night R&B Experience"
  },
  "add-ticket": {
    title: "Add a Sample Ticket Sale",
    text: "Enter a sample customer or ticket note. This does not process a real payment.",
    placeholder: "Example: 2 General Admission tickets"
  },
  "add-member": {
    title: "Add a Sample Member",
    text: "Add a temporary sample membership record to experience the workflow.",
    placeholder: "Example: Jordan Smith"
  },
  "add-expense": {
    title: "Add a Sample Expense",
    text: "Enter a sample business expense. No financial account is connected.",
    placeholder: "Example: Venue deposit - $500"
  }
};

const tourSteps = [
  {
    target: '[data-tour="welcome"]',
    title: "Dashboard Overview",
    description:
      "This welcome area gives the business owner a quick summary and immediate access to common actions."
  },
  {
    target: '[data-tour="metrics"]',
    title: "Key Business Metrics",
    description:
      "Important numbers such as ticket sales, attendance, memberships, and revenue are displayed in one place."
  },
  {
    target: '[data-tour="events"]',
    title: "Event Management",
    description:
      "Upcoming events can be reviewed alongside ticket totals, progress, dates, and event status."
  },
  {
    target: '[data-tour="revenue"]',
    title: "Revenue Reporting",
    description:
      "Visual reporting helps the business compare performance and understand where revenue is coming from."
  },
  {
    target: '[data-tour="activity"]',
    title: "Recent Activity",
    description:
      "The activity feed shows recent sales, memberships, expenses, and other important updates."
  },
  {
    target: '[data-tour="quick-actions"]',
    title: "Quick Actions",
    description:
      "Frequently used tasks are placed within easy reach so the dashboard is faster and easier to manage."
  }
];

function showToast(message) {
  clearTimeout(toastTimer);
  demoToast.textContent = message;
  demoToast.classList.add("is-visible");

  toastTimer = setTimeout(() => {
    demoToast.classList.remove("is-visible");
  }, 3000);
}

function closeModal(modal) {
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
}

function openModal(modal) {
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function switchView(viewName) {
  dashboardViews.forEach((view) => {
    view.classList.toggle("active", view.id === `view-${viewName}`);
  });

  navItems.forEach((item) => {
    item.classList.toggle("active", item.dataset.view === viewName);
  });

  const activeView = document.getElementById(`view-${viewName}`);

  if (activeView) {
    pageTitle.textContent = activeView.dataset.title || "Dashboard";
  }

  sidebar.classList.remove("is-open");
  mobileMenuButton.setAttribute("aria-expanded", "false");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
}

function formatDate(value) {
  const date = new Date(`${value}T12:00:00`);

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(date);
}

function renderEvents() {
  const searchTerm = eventSearch.value.trim().toLowerCase();
  const selectedStatus = eventStatusFilter.value;

  const filteredEvents = demoEvents.filter((event) => {
    const matchesSearch = event.name.toLowerCase().includes(searchTerm);
    const matchesStatus =
      selectedStatus === "all" || event.status === selectedStatus;

    return matchesSearch && matchesStatus;
  });

  if (!filteredEvents.length) {
    eventsTableBody.innerHTML = `
      <tr>
        <td colspan="6">No sample events match the current filters.</td>
      </tr>
    `;
    return;
  }

  eventsTableBody.innerHTML = filteredEvents
    .map(
      (event, index) => `
        <tr>
          <td><strong>${event.name}</strong></td>
          <td>${formatDate(event.date)}</td>
          <td>${event.tickets}</td>
          <td>${formatCurrency(event.revenue)}</td>
          <td>
            <span class="status-badge ${event.status.toLowerCase()}">
              ${event.status}
            </span>
          </td>
          <td>
            <button
              class="table-action"
              type="button"
              data-edit-event="${index}"
            >
              Edit
            </button>
          </td>
        </tr>
      `
    )
    .join("");
}

function updateMetrics() {
  const totalTickets = demoEvents.reduce(
    (total, event) => total + Number(event.tickets || 0),
    0
  );

  const totalRevenue = demoEvents.reduce(
    (total, event) => total + Number(event.revenue || 0),
    0
  );

  document.getElementById("metricTickets").textContent = totalTickets;
  document.getElementById("metricAttendance").textContent =
    totalTickets + 38;
  document.getElementById("metricRevenue").textContent =
    formatCurrency(totalRevenue + 760);
}

function openAction(actionName) {
  const content = actionContent[actionName];

  if (!content) {
    return;
  }

  currentAction = actionName;
  actionModalTitle.textContent = content.title;
  actionModalText.textContent = content.text;
  demoActionInput.placeholder = content.placeholder;
  demoActionInput.value = "";

  openModal(actionModal);

  setTimeout(() => {
    demoActionInput.focus();
  }, 100);
}

function saveDemoAction(value) {
  if (currentAction === "create-event") {
    demoEvents.unshift({
      name: value,
      date: "2026-09-12",
      tickets: 0,
      revenue: 0,
      status: "Draft"
    });

    renderEvents();
    updateMetrics();
    showToast("Sample event added successfully.");
    return;
  }

  if (currentAction === "add-ticket") {
    const firstUpcomingEvent = demoEvents.find(
      (event) => event.status === "Upcoming"
    );

    if (firstUpcomingEvent) {
      firstUpcomingEvent.tickets += 1;
      firstUpcomingEvent.revenue += 20;
    }

    renderEvents();
    updateMetrics();
    showToast("Sample ticket sale added.");
    return;
  }

  if (currentAction === "add-member") {
    const memberMetric = document.getElementById("metricMembers");
    memberMetric.textContent = Number(memberMetric.textContent) + 1;
    showToast(`Sample member "${value}" added.`);
    return;
  }

  if (currentAction === "add-expense") {
    showToast(`Sample expense saved: ${value}`);
  }
}

function clearTourHighlight() {
  document.querySelectorAll(".tour-highlight").forEach((element) => {
    element.classList.remove("tour-highlight");
  });
}


function positionTourOverlay(target) {
  const gap = 22;
  const padding = 18;
  const overlayWidth = Math.min(420, window.innerWidth - 36);

  const targetRect = target.getBoundingClientRect();
  const estimatedHeight = tourOverlay.offsetHeight || 280;

  const roomRight = window.innerWidth - targetRect.right;
  const roomLeft = targetRect.left;
  const roomBelow = window.innerHeight - targetRect.bottom;
  const roomAbove = targetRect.top;

  let left;
  let top;

  if (roomRight >= overlayWidth + gap) {
    left = targetRect.right + gap;
    top = targetRect.top;
  } else if (roomLeft >= overlayWidth + gap) {
    left = targetRect.left - overlayWidth - gap;
    top = targetRect.top;
  } else if (roomBelow >= estimatedHeight + gap) {
    left = targetRect.left;
    top = targetRect.bottom + gap;
  } else if (roomAbove >= estimatedHeight + gap) {
    left = targetRect.left;
    top = targetRect.top - estimatedHeight - gap;
  } else {
    left = window.innerWidth - overlayWidth - padding;
    top = window.innerHeight - estimatedHeight - padding;
  }

  left = Math.max(
    padding,
    Math.min(left, window.innerWidth - overlayWidth - padding)
  );

  top = Math.max(
    padding,
    Math.min(top, window.innerHeight - estimatedHeight - padding)
  );

  tourOverlay.style.left = `${left}px`;
  tourOverlay.style.top = `${top}px`;
  tourOverlay.style.right = "auto";
  tourOverlay.style.bottom = "auto";
  tourOverlay.style.width = `${overlayWidth}px`;
}

function displayTourStep() {
  clearTourHighlight();

  const step = tourSteps[currentTourStep];
  const target = document.querySelector(step.target);

  tourStepLabel.textContent =
    `Step ${currentTourStep + 1} of ${tourSteps.length}`;
  tourTitle.textContent = step.title;
  tourDescription.textContent = step.description;

  tourBackButton.disabled = currentTourStep === 0;
  tourNextButton.textContent =
    currentTourStep === tourSteps.length - 1 ? "Finish Tour" : "Next";

  if (target) {
    target.classList.add("tour-highlight");
    target.scrollIntoView({
      behavior: "smooth",
      block: "center"
    });

    setTimeout(() => {
      positionTourOverlay(target);
    }, 350);
  }
}

function startTour() {
  closeModal(welcomeModal);
  switchView("overview");
  currentTourStep = 0;
  tourOverlay.classList.add("is-open");
  tourOverlay.setAttribute("aria-hidden", "false");
  displayTourStep();
}

function endTour() {
  clearTourHighlight();
  tourOverlay.classList.remove("is-open");
  tourOverlay.setAttribute("aria-hidden", "true");
  showToast("Guided tour ended. Continue exploring the dashboard.");
}

function resetDemo() {
  demoEvents = structuredClone(initialEvents);

  eventSearch.value = "";
  eventStatusFilter.value = "all";

  document.getElementById("metricMembers").textContent = "34";

  renderEvents();
  updateMetrics();
  switchView("overview");
  closeModal(actionModal);
  endTour();

  showToast("The interactive demo has been reset.");
}

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    switchView(item.dataset.view);
  });
});

document.querySelectorAll("[data-switch-view]").forEach((button) => {
  button.addEventListener("click", () => {
    switchView(button.dataset.switchView);
  });
});

document.querySelectorAll("[data-demo-action]").forEach((button) => {
  button.addEventListener("click", () => {
    openAction(button.dataset.demoAction);
  });
});

document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", () => {
    closeModal(button.closest(".demo-modal"));
  });
});

document.querySelectorAll(".demo-modal").forEach((modal) => {
  modal.addEventListener("click", (event) => {
    if (event.target === modal) {
      closeModal(modal);
    }
  });
});

mobileMenuButton.addEventListener("click", () => {
  const isOpen = sidebar.classList.toggle("is-open");
  mobileMenuButton.setAttribute("aria-expanded", String(isOpen));
});

document.getElementById("exploreDemoButton").addEventListener("click", () => {
  closeModal(welcomeModal);
  showToast("You are now exploring the sample dashboard.");
});

document.getElementById("welcomeStartTour").addEventListener("click", startTour);
document.getElementById("startTourButton").addEventListener("click", startTour);
document.getElementById("endTourButton").addEventListener("click", endTour);

document.getElementById("resetDemoButton").addEventListener("click", () => {
  const confirmed = window.confirm(
    "Reset all temporary demo changes and restore the original sample information?"
  );

  if (confirmed) {
    resetDemo();
  }
});

tourNextButton.addEventListener("click", () => {
  if (currentTourStep === tourSteps.length - 1) {
    endTour();
    showToast("Tour complete. Try making a sample change.");
    return;
  }

  currentTourStep += 1;
  displayTourStep();
});

tourBackButton.addEventListener("click", () => {
  if (currentTourStep > 0) {
    currentTourStep -= 1;
    displayTourStep();
  }
});

demoActionForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const value = demoActionInput.value.trim();

  if (!value) {
    return;
  }

  saveDemoAction(value);
  closeModal(actionModal);
});

eventSearch.addEventListener("input", renderEvents);
eventStatusFilter.addEventListener("change", renderEvents);

eventsTableBody.addEventListener("click", (event) => {
  const editButton = event.target.closest("[data-edit-event]");

  if (!editButton) {
    return;
  }

  showToast(
    "In a live dashboard, this button would open the full event editor."
  );
});

document.querySelector(".disabled-live-action").addEventListener("click", () => {
  showToast(
    "Live payment integrations are intentionally disabled in this public demo."
  );
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModal(actionModal);
    closeModal(welcomeModal);
    endTour();
  }
});

renderEvents();
updateMetrics();

window.addEventListener("resize", () => {
  if (!tourOverlay.classList.contains("is-open")) {
    return;
  }

  const step = tourSteps[currentTourStep];
  const target = document.querySelector(step.target);

  if (target) {
    positionTourOverlay(target);
  }
});

const mobileDashboardGate = document.getElementById("mobileDashboardGate");
const continueMobileDemo = document.getElementById("continueMobileDemo");

function updateMobileDashboardGate() {
  const isMobile = window.matchMedia("(max-width: 767px)").matches;
  const wasDismissed =
    sessionStorage.getItem("hovMobileDashboardDismissed") === "true";

  if (!mobileDashboardGate) {
    return;
  }

  if (isMobile && !wasDismissed) {
    mobileDashboardGate.classList.remove("is-dismissed");
    document.body.classList.add("mobile-demo-locked");
  } else {
    mobileDashboardGate.classList.add("is-dismissed");
    document.body.classList.remove("mobile-demo-locked");
  }
}

if (continueMobileDemo) {
  continueMobileDemo.addEventListener("click", () => {
    sessionStorage.setItem("hovMobileDashboardDismissed", "true");
    mobileDashboardGate.classList.add("is-dismissed");
    document.body.classList.remove("mobile-demo-locked");
  });
}

window.addEventListener("resize", updateMobileDashboardGate);
updateMobileDashboardGate();
