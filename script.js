const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector("#siteNav");
const navLinks = [...document.querySelectorAll("#siteNav a")];
const revealItems = [...document.querySelectorAll(".reveal")];
const counters = [...document.querySelectorAll(".counter")];
const stickyCta = document.querySelector("#stickyCta");
const ctaModal = document.querySelector("#ctaModal");
const modalClose = document.querySelector("#modalClose");
const filterWrap = document.querySelector("#portfolioFilters");
const filterButtons = [...document.querySelectorAll(".filter-btn")];
const portfolioItems = [...document.querySelectorAll(".portfolio-item")];
const templateFilterWrap = document.querySelector("#templateFilters");
const templateItems = [...document.querySelectorAll(".template-item")];
const previewToggle = document.querySelector("#previewToggle");
const previewImage = document.querySelector("#previewImage");
const tryDemoButtons = [...document.querySelectorAll(".try-demo-btn")];
const templateDemoModal = document.querySelector("#templateDemoModal");
const templateDemoClose = document.querySelector("#templateDemoClose");
const templateDemoTitle = document.querySelector("#templateDemoTitle");
const demoResetBtn = document.querySelector("#demoResetBtn");
const demoPreviewBtn = document.querySelector("#demoPreviewBtn");
const templateEditorCanvas = document.querySelector("#templateEditorCanvas");
const editorToolButtons = [...document.querySelectorAll(".editor-tool-btn")];
const demoCanvasBg = document.querySelector("#demoCanvasBg");
const demoAccentColor = document.querySelector("#demoAccentColor");
const demoLogoUpload = document.querySelector("#demoLogoUpload");
const demoImageUpload = document.querySelector("#demoImageUpload");
const demoFontFamily = document.querySelector("#demoFontFamily");
const demoFontSize = document.querySelector("#demoFontSize");
const demoTextColor = document.querySelector("#demoTextColor");
const demoOpacity = document.querySelector("#demoOpacity");
const alignButtons = [...document.querySelectorAll(".align-btn")];
const effectShadow = document.querySelector("#effectShadow");
const effectBorder = document.querySelector("#effectBorder");
const effectRounded = document.querySelector("#effectRounded");
const effectGlow = document.querySelector("#effectGlow");
const bringForwardBtn = document.querySelector("#bringForwardBtn");
const sendBackwardBtn = document.querySelector("#sendBackwardBtn");
const deleteSelectedBtn = document.querySelector("#deleteSelectedBtn");
const clearAddedBtn = document.querySelector("#clearAddedBtn");
const demoDeviceToggle = document.querySelector("#demoDeviceToggle");
const serviceExpanders = [...document.querySelectorAll(".service-expand")];
const jukeboxCarousel = document.querySelector("#jukeboxCarousel");
const jukeboxTrack = document.querySelector("#jukeboxTrack");
const jukeboxPrev = document.querySelector("#jukeboxPrev");
const jukeboxNext = document.querySelector("#jukeboxNext");
const jukeboxDots = document.querySelector("#jukeboxDots");
const contentCarousel = document.querySelector("#contentCarousel");
const contentCarouselTrack = document.querySelector("#contentCarouselTrack");
const contentPrev = document.querySelector("#contentPrev");
const contentNext = document.querySelector("#contentNext");
const contentDots = document.querySelector("#contentDots");
const zoomTargets = [
  ...document.querySelectorAll(".media img"),
  ...document.querySelectorAll(".preview-image img"),
  ...document.querySelectorAll(".hero-inspiration"),
  ...document.querySelectorAll(".bold-hero-image"),
  ...document.querySelectorAll(".device-showcase-card img"),
  ...document.querySelectorAll(".content-slide-image img"),
  ...document.querySelectorAll(".realtor-media img")
];

if (menuToggle && nav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = nav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });
}

navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    nav?.classList.remove("open");
    menuToggle?.setAttribute("aria-expanded", "false");
  });
});

function animateCounter(el) {
  const target = Number(el.dataset.target || 0);
  let current = 0;
  const step = Math.max(1, Math.ceil(target / 45));
  const timer = setInterval(() => {
    current += step;
    if (current >= target) {
      current = target;
      clearInterval(timer);
    }
    const suffix = target === 3 ? "x" : target === 100 ? "+" : "%";
    el.textContent = `${current}${suffix}`;
  }, 26);
}

const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in-view");
        if (entry.target.classList.contains("counter")) {
          animateCounter(entry.target);
        }
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.18 }
);

revealItems.forEach((item) => revealObserver.observe(item));
counters.forEach((counter) => revealObserver.observe(counter));

if (stickyCta && ctaModal) {
  stickyCta.addEventListener("click", () => ctaModal.classList.add("open"));
}

if (modalClose && ctaModal) {
  modalClose.addEventListener("click", () => ctaModal.classList.remove("open"));
  ctaModal.addEventListener("click", (event) => {
    if (event.target === ctaModal) ctaModal.classList.remove("open");
  });
}

function applyPortfolioFilter(filter) {
  portfolioItems.forEach((item) => {
    const kinds = (item.dataset.kind || "").split(/\s+/);
    const visible = filter === "all" || kinds.includes(filter);
    item.classList.toggle("is-hidden", !visible);
  });
}

if (filterWrap && filterButtons.length) {
  filterWrap.addEventListener("click", (event) => {
    const btn = event.target.closest(".filter-btn");
    if (!btn) return;
    const scopedButtons = [...filterWrap.querySelectorAll(".filter-btn")];
    scopedButtons.forEach((button) => button.classList.remove("active"));
    btn.classList.add("active");
    applyPortfolioFilter(btn.dataset.filter || "all");
  });
}

function applyTemplateFilter(filter) {
  templateItems.forEach((item) => {
    const kinds = (item.dataset.templateKind || "").split(/\s+/).filter(Boolean);
    const visible = filter === "all" || kinds.includes(filter);
    item.classList.toggle("is-hidden", !visible);
  });
}

if (templateFilterWrap && templateItems.length) {
  templateFilterWrap.addEventListener("click", (event) => {
    const btn = event.target.closest(".filter-btn");
    if (!btn) return;
    const scopedButtons = [...templateFilterWrap.querySelectorAll(".filter-btn")];
    scopedButtons.forEach((button) => button.classList.remove("active"));
    btn.classList.add("active");
    applyTemplateFilter(btn.dataset.templateFilter || "all");
  });
}

if (previewToggle && previewImage) {
  const previewMap = {
    canva: "./event-promo-social-feed-mockup.png",
    flyer: "./event-promo-event-flyer-mockup.png",
    social: "./event-promo-social-feed-mockup.png"
  };

  previewToggle.addEventListener("click", (event) => {
    const btn = event.target.closest(".filter-btn");
    if (!btn) return;
    const target = btn.dataset.previewTarget;
    if (!target || !previewMap[target]) return;
    const buttons = [...previewToggle.querySelectorAll(".filter-btn")];
    buttons.forEach((button) => button.classList.remove("active"));
    btn.classList.add("active");
    previewImage.src = previewMap[target];
  });
}

if (tryDemoButtons.length && templateDemoModal) {
  let selectedElement = null;
  let dragState = null;
  let elementCounter = 1;
  let previewMode = false;

  const selectElement = (el) => {
    if (!templateEditorCanvas || !el) return;
    templateEditorCanvas.querySelectorAll(".canvas-element").forEach((item) => item.classList.remove("is-selected"));
    selectedElement = el;
    selectedElement.classList.add("is-selected");
    if (demoFontSize) demoFontSize.value = parseInt(window.getComputedStyle(selectedElement).fontSize, 10) || 28;
    if (demoOpacity) demoOpacity.value = String(Math.round(((parseFloat(selectedElement.style.opacity) || 1) * 100)));
  };

  const createCanvasElement = (type, text = "") => {
    const el = document.createElement("div");
    el.className = "canvas-element";
    el.dataset.elementType = type;
    el.dataset.seed = "false";
    el.style.left = `${12 + (elementCounter % 4) * 7}%`;
    el.style.top = `${12 + (elementCounter % 6) * 8}%`;
    el.style.zIndex = String(10 + elementCounter);
    elementCounter += 1;

    if (type === "heading") {
      el.classList.add("is-heading");
      el.textContent = text || "Heading Text";
      el.contentEditable = "true";
    } else if (type === "subheading") {
      el.classList.add("is-subheading");
      el.textContent = text || "Subheading text";
      el.contentEditable = "true";
    } else if (type === "button") {
      el.classList.add("is-button");
      el.textContent = text || "Call To Action";
      el.contentEditable = "true";
    } else if (type === "shape") {
      el.classList.add("is-shape");
      el.textContent = "";
      el.contentEditable = "false";
    } else if (type === "image") {
      el.classList.add("is-image");
      el.textContent = "Image";
      el.contentEditable = "false";
    } else {
      el.textContent = text || "Text box";
      el.contentEditable = "true";
    }

    return el;
  };

  const applyEffects = () => {
    if (!selectedElement) return;
    selectedElement.style.boxShadow = effectShadow?.checked ? "0 8px 18px rgba(0,0,0,.18)" : "none";
    selectedElement.style.border = effectBorder?.checked ? "1px solid rgba(31,122,87,.55)" : "none";
    selectedElement.style.borderRadius = effectRounded?.checked ? "10px" : "0";
    selectedElement.style.filter = effectGlow?.checked ? "drop-shadow(0 0 8px rgba(201,162,79,.6))" : "none";
  };

  const openDemo = (templateName, templateImageSrc) => {
    if (templateDemoTitle) templateDemoTitle.textContent = `${templateName} Demo`;
    if (templateEditorCanvas) {
      templateEditorCanvas.style.backgroundImage = "none";
      templateEditorCanvas.style.backgroundColor = "#ffffff";
    }
    previewMode = false;
    templateDemoModal.classList.remove("preview-mode");
    templateDemoModal.classList.add("open");
    templateDemoModal.setAttribute("aria-hidden", "false");
    resetDemo();
  };

  const closeDemo = () => {
    templateDemoModal.classList.remove("open");
    templateDemoModal.classList.remove("preview-mode");
    templateDemoModal.setAttribute("aria-hidden", "true");
    previewMode = false;
  };

  const resetDemo = () => {
    if (!templateEditorCanvas) return;
    templateEditorCanvas.innerHTML = "";
    const seed = [
      createCanvasElement("heading", "Add Heading"),
      createCanvasElement("subheading", "Add Subheading"),
      createCanvasElement("text", "Add Your Text"),
      createCanvasElement("button", "Add Button Text"),
      createCanvasElement("image", "Upload Logo"),
      createCanvasElement("image", "Upload Image")
    ];
    seed[0].style.left = "8%";
    seed[0].style.top = "10%";
    seed[1].style.left = "8%";
    seed[1].style.top = "20%";
    seed[2].style.left = "8%";
    seed[2].style.top = "30%";
    seed[3].style.left = "8%";
    seed[3].style.top = "41%";
    seed[4].style.left = "63%";
    seed[4].style.top = "10%";
    seed[5].style.left = "56%";
    seed[5].style.top = "32%";

    seed.forEach((el, index) => {
      el.dataset.seed = "true";
      if (index > 0) el.classList.remove("is-selected");
      templateEditorCanvas.appendChild(el);
    });
    const watermark = document.createElement("div");
    watermark.className = "demo-watermark";
    watermark.setAttribute("aria-hidden", "true");
    templateEditorCanvas.prepend(watermark);
    selectElement(seed[0]);
    templateEditorCanvas.style.backgroundColor = "#ffffff";
    templateEditorCanvas.style.backgroundImage = "none";
    if (demoCanvasBg) demoCanvasBg.value = "#ffffff";
  };

  tryDemoButtons.forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      const card = btn.closest(".template-card");
      const title = card?.querySelector("h3")?.textContent?.trim() || "Template";
      const templateImageSrc = card?.querySelector(".preview img")?.getAttribute("src") || "";
      openDemo(title, templateImageSrc);
    });
  });

  templateDemoClose?.addEventListener("click", closeDemo);
  templateDemoModal.addEventListener("click", (event) => {
    if (event.target === templateDemoModal) closeDemo();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && templateDemoModal.classList.contains("open")) {
      closeDemo();
    }
  });

  if (templateEditorCanvas) {
    templateEditorCanvas.addEventListener("click", (event) => {
      const target = event.target.closest(".canvas-element");
      if (!target) return;
      selectElement(target);
    });

    templateEditorCanvas.addEventListener("pointerdown", (event) => {
      const target = event.target.closest(".canvas-element");
      if (!target) return;
      selectElement(target);
      const canvasRect = templateEditorCanvas.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      dragState = {
        el: target,
        offsetX: event.clientX - targetRect.left,
        offsetY: event.clientY - targetRect.top,
        canvasRect
      };
      target.setPointerCapture?.(event.pointerId);
    });

    templateEditorCanvas.addEventListener("pointermove", (event) => {
      if (!dragState) return;
      const { el, offsetX, offsetY, canvasRect } = dragState;
      const x = event.clientX - canvasRect.left - offsetX;
      const y = event.clientY - canvasRect.top - offsetY;
      const leftPct = Math.max(0, Math.min(95, (x / canvasRect.width) * 100));
      const topPct = Math.max(0, Math.min(95, (y / canvasRect.height) * 100));
      el.style.left = `${leftPct}%`;
      el.style.top = `${topPct}%`;
    });

    templateEditorCanvas.addEventListener("pointerup", () => {
      dragState = null;
    });
  }

  editorToolButtons.forEach((button) => {
    button.addEventListener("click", () => {
      if (!templateEditorCanvas) return;
      const type = button.dataset.addType || "text";
      const el = createCanvasElement(type);
      templateEditorCanvas.appendChild(el);
      selectElement(el);
    });
  });

  if (demoCanvasBg && templateEditorCanvas) {
    demoCanvasBg.addEventListener("input", () => {
      templateEditorCanvas.style.backgroundImage = "none";
      templateEditorCanvas.style.backgroundColor = demoCanvasBg.value;
    });
  }

  if (demoAccentColor) {
    demoAccentColor.addEventListener("input", () => {
      if (!selectedElement) return;
      selectedElement.style.color = demoAccentColor.value;
      if (selectedElement.classList.contains("is-button") || selectedElement.classList.contains("is-shape")) {
        selectedElement.style.background = demoAccentColor.value;
      }
    });
  }

  if (demoFontFamily) {
    demoFontFamily.addEventListener("change", () => {
      if (!selectedElement) return;
      selectedElement.style.fontFamily = demoFontFamily.value;
    });
  }

  if (demoFontSize) {
    demoFontSize.addEventListener("input", () => {
      if (!selectedElement) return;
      selectedElement.style.fontSize = `${demoFontSize.value}px`;
    });
  }

  if (demoTextColor) {
    demoTextColor.addEventListener("input", () => {
      if (!selectedElement) return;
      selectedElement.style.color = demoTextColor.value;
    });
  }

  if (demoOpacity) {
    demoOpacity.addEventListener("input", () => {
      if (!selectedElement) return;
      selectedElement.style.opacity = String(Number(demoOpacity.value) / 100);
    });
  }

  alignButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!selectedElement) return;
      selectedElement.style.textAlign = btn.dataset.align || "left";
    });
  });

  [effectShadow, effectBorder, effectRounded, effectGlow].forEach((control) => {
    control?.addEventListener("change", applyEffects);
  });

  bringForwardBtn?.addEventListener("click", () => {
    if (!selectedElement) return;
    const z = Number(selectedElement.style.zIndex || 10);
    selectedElement.style.zIndex = String(z + 1);
  });

  sendBackwardBtn?.addEventListener("click", () => {
    if (!selectedElement) return;
    const z = Number(selectedElement.style.zIndex || 10);
    selectedElement.style.zIndex = String(Math.max(1, z - 1));
  });

  deleteSelectedBtn?.addEventListener("click", () => {
    if (!selectedElement || !templateEditorCanvas) return;
    if (selectedElement.dataset.seed === "true") {
      const isLogoSlot = selectedElement.style.left === "63%" && selectedElement.style.top === "10%";
      const resetText = selectedElement.dataset.elementType === "image"
        ? (isLogoSlot ? "Upload Logo" : "Upload Image")
        : selectedElement.dataset.elementType === "heading"
          ? "Add Heading"
          : selectedElement.dataset.elementType === "subheading"
            ? "Add Subheading"
            : selectedElement.dataset.elementType === "button"
              ? "Add Button Text"
              : "Add Your Text";
      selectedElement.innerHTML = resetText;
      selectedElement.style.fontFamily = "";
      selectedElement.style.fontSize = "";
      selectedElement.style.color = "";
      selectedElement.style.opacity = "";
      selectedElement.style.textAlign = "";
      selectedElement.style.boxShadow = "";
      selectedElement.style.border = "";
      selectedElement.style.borderRadius = "";
      selectedElement.style.filter = "";
      if (selectedElement.classList.contains("is-button")) {
        selectedElement.style.background = "";
      }
      return;
    }
    const toRemove = selectedElement;
    selectedElement = null;
    toRemove.remove();
    const next = templateEditorCanvas.querySelector(".canvas-element");
    if (next) selectElement(next);
  });

  clearAddedBtn?.addEventListener("click", () => {
    if (!templateEditorCanvas) return;
    templateEditorCanvas.querySelectorAll(".canvas-element").forEach((el) => {
      if (el.dataset.seed !== "true") el.remove();
    });
    const firstSeed = templateEditorCanvas.querySelector('.canvas-element[data-seed="true"]');
    if (firstSeed) selectElement(firstSeed);
  });

  demoLogoUpload?.addEventListener("change", () => {
    const [file] = demoLogoUpload.files || [];
    if (!file || !templateEditorCanvas) return;
    const url = URL.createObjectURL(file);
    const el = createCanvasElement("image");
    el.innerHTML = `<img src="${url}" alt="Temporary uploaded logo" />`;
    el.classList.add("is-logo");
    templateEditorCanvas.appendChild(el);
    selectElement(el);
  });

  demoImageUpload?.addEventListener("change", () => {
    const [file] = demoImageUpload.files || [];
    if (!file || !templateEditorCanvas) return;
    const url = URL.createObjectURL(file);
    const el = createCanvasElement("image");
    el.innerHTML = `<img src="${url}" alt="Temporary uploaded image" />`;
    templateEditorCanvas.appendChild(el);
    selectElement(el);
  });

  demoResetBtn?.addEventListener("click", () => {
    resetDemo();
  });

  demoPreviewBtn?.addEventListener("click", () => {
    previewMode = !previewMode;
    templateDemoModal.classList.toggle("preview-mode", previewMode);
    demoPreviewBtn.textContent = previewMode ? "Exit Preview" : "Preview";
  });

  if (demoDeviceToggle && templateEditorCanvas) {
    demoDeviceToggle.addEventListener("click", (event) => {
      const btn = event.target.closest(".filter-btn");
      if (!btn) return;
      const target = btn.dataset.demoDevice;
      const buttons = [...demoDeviceToggle.querySelectorAll(".filter-btn")];
      buttons.forEach((button) => button.classList.remove("active"));
      btn.classList.add("active");
      templateEditorCanvas.classList.toggle("is-mobile", target === "mobile");
    });
  }

  if (templateEditorCanvas && !templateEditorCanvas.querySelector(".canvas-element")) {
    resetDemo();
  }
}

if (zoomTargets.length) {
  const lightbox = document.createElement("div");
  lightbox.className = "image-lightbox";
  lightbox.setAttribute("aria-hidden", "true");
  lightbox.innerHTML = '<img alt="Expanded project image preview" />';
  document.body.appendChild(lightbox);

  const lightboxImage = lightbox.querySelector("img");

  function closeLightbox() {
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    lightboxImage.removeAttribute("src");
  }

  zoomTargets.forEach((img) => {
    img.classList.add("zoomable-image");
    img.addEventListener("click", () => {
      lightboxImage.src = img.currentSrc || img.src;
      lightbox.classList.add("open");
      lightbox.setAttribute("aria-hidden", "false");
    });
  });

  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox || event.target === lightboxImage) {
      closeLightbox();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && lightbox.classList.contains("open")) {
      closeLightbox();
    }
  });
}

if (serviceExpanders.length) {
  serviceExpanders.forEach((detailsEl) => {
    const summary = detailsEl.querySelector("summary");
    if (!summary) return;

    summary.addEventListener("click", (event) => {
      event.preventDefault();
      detailsEl.open = !detailsEl.open;
    });
  });
}

if (jukeboxCarousel && jukeboxTrack && jukeboxDots) {
  const slides = [...jukeboxTrack.querySelectorAll(".carousel-slide")];
  let current = 0;

  function renderDots() {
    jukeboxDots.innerHTML = "";
    slides.forEach((_, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = `carousel-dot${index === current ? " active" : ""}`;
      dot.setAttribute("aria-label", `Go to screenshot ${index + 1}`);
      dot.addEventListener("click", () => {
        current = index;
        updateCarousel();
      });
      jukeboxDots.appendChild(dot);
    });
  }

  function updateCarousel() {
    jukeboxTrack.style.transform = `translateX(-${current * 100}%)`;
    [...jukeboxDots.children].forEach((dot, idx) => {
      dot.classList.toggle("active", idx === current);
    });
  }

  function nextSlide() {
    current = (current + 1) % slides.length;
    updateCarousel();
  }

  function prevSlide() {
    current = (current - 1 + slides.length) % slides.length;
    updateCarousel();
  }

  jukeboxNext?.addEventListener("click", () => {
    nextSlide();
  });

  jukeboxPrev?.addEventListener("click", () => {
    prevSlide();
  });

  renderDots();
  updateCarousel();
}

if (contentCarousel && contentCarouselTrack && contentDots) {
  const slides = [...contentCarouselTrack.querySelectorAll(".content-slide")];
  let current = 0;

  function renderDots() {
    contentDots.innerHTML = "";
    slides.forEach((_, index) => {
      const dot = document.createElement("button");
      dot.type = "button";
      dot.className = `carousel-dot${index === current ? " active" : ""}`;
      dot.setAttribute("aria-label", `Go to content slide ${index + 1}`);
      dot.addEventListener("click", () => {
        current = index;
        updateCarousel();
      });
      contentDots.appendChild(dot);
    });
  }

  function updateCarousel() {
    contentCarouselTrack.style.transform = `translateX(-${current * 100}%)`;
    [...contentDots.children].forEach((dot, idx) => {
      dot.classList.toggle("active", idx === current);
    });
  }

  function nextSlide() {
    current = (current + 1) % slides.length;
    updateCarousel();
  }

  function prevSlide() {
    current = (current - 1 + slides.length) % slides.length;
    updateCarousel();
  }

  contentNext?.addEventListener("click", () => {
    nextSlide();
  });

  contentPrev?.addEventListener("click", () => {
    prevSlide();
  });

  renderDots();
  updateCarousel();
}

const contactForm = document.querySelector("#contactForm");
const formSuccess = document.querySelector("#formSuccess");
const testimonialForm = document.querySelector("#testimonialForm");
const testimonialSuccess = document.querySelector("#testimonialSuccess");
const referralSource = document.querySelector("#referralSource");
const referralNameWrap = document.querySelector("#referralNameWrap");
const referralNameInput = document.querySelector("#referralName");

function toggleReferralField() {
  if (!referralSource || !referralNameWrap) return;
  const isReferral = referralSource.value === "Referral";
  referralNameWrap.hidden = !isReferral;
  if (referralNameInput) {
    referralNameInput.required = isReferral;
    if (!isReferral) referralNameInput.value = "";
  }
}

if (contactForm) {
  const projectTypeChecks = [...contactForm.querySelectorAll('input[name="project_type[]"]')];
  const projectGoalChecks = [...contactForm.querySelectorAll('input[name="project_goal[]"]')];
  const projectTypeFieldset = projectTypeChecks[0]?.closest(".checkbox-fieldset");
  const projectGoalFieldset = projectGoalChecks[0]?.closest(".checkbox-fieldset");

  function validateCheckboxGroup(checkboxes, message, fieldset) {
    if (!checkboxes.length) return true;
    const checked = checkboxes.some((cb) => cb.checked);
    checkboxes[0].setCustomValidity(checked ? "" : message);
    fieldset?.classList.toggle("is-invalid", !checked);
    return checked;
  }

  toggleReferralField();
  referralSource?.addEventListener("change", toggleReferralField);
  projectTypeChecks.forEach((cb) =>
    cb.addEventListener("change", () => validateCheckboxGroup(projectTypeChecks, "Please select at least one project type.", projectTypeFieldset))
  );
  projectGoalChecks.forEach((cb) =>
    cb.addEventListener("change", () => validateCheckboxGroup(projectGoalChecks, "Please select at least one project goal.", projectGoalFieldset))
  );
  contactForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const typeValid = validateCheckboxGroup(projectTypeChecks, "Please select at least one project type.", projectTypeFieldset);
    const goalValid = validateCheckboxGroup(projectGoalChecks, "Please select at least one project goal.", projectGoalFieldset);
    if (!typeValid || !goalValid || !contactForm.reportValidity()) return;
    if (formSuccess) {
      formSuccess.hidden = true;
      formSuccess.textContent = "";
    }

    const submitButton = contactForm.querySelector('button[type="submit"]');
    const originalButtonText = submitButton?.textContent || "Submit Inquiry";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Sending...";
    }

    let fallbackMailto = "";

    try {
      const formData = new FormData(contactForm);
      const params = new URLSearchParams();

      for (const [key, value] of formData.entries()) {
        if (value instanceof File) continue;
        params.append(key, value);
      }

      fallbackMailto = `mailto:hello@houseofvisualsco.com?subject=${encodeURIComponent("New House of Visuals Inquiry")}&body=${encodeURIComponent(
        [...params.entries()].map(([key, value]) => `${key.replace(/\[\]$/, "")}: ${value}`).join("\n")
      )}`;

      const response = await fetch("/api/inquiry", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body: params.toString(),
      });
      const result = await response.json().catch(() => ({
        ok: false,
        message: "The inquiry service is not available from this server."
      }));

      if (!response.ok || !result.ok) {
        throw new Error(result.message || "We could not send your inquiry right now.");
      }

      if (formSuccess) {
        formSuccess.hidden = false;
        formSuccess.textContent = result.message || "Thank you! Your inquiry has been received. We’ll review your details and follow up soon.";
        formSuccess.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      contactForm.reset();
      toggleReferralField();
    } catch (error) {
      if (formSuccess) {
        formSuccess.hidden = false;
        const cannotReachServer = error instanceof TypeError || /failed to fetch|not available from this server/i.test(error.message || "");
        formSuccess.textContent = cannotReachServer
          ? "We could not reach the inquiry service from this page. Please send your inquiry directly to hello@houseofvisualsco.com."
          : error.message || "Something went wrong while sending your inquiry. Please try again.";
        if (cannotReachServer && fallbackMailto) {
          const fallbackLink = document.createElement("a");
          fallbackLink.href = fallbackMailto;
          fallbackLink.textContent = " Open email draft";
          fallbackLink.style.fontWeight = "700";
          formSuccess.appendChild(fallbackLink);
        }
        formSuccess.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
      }
    }
  });
}

if (testimonialForm) {
  testimonialForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!testimonialForm.reportValidity()) return;

    if (testimonialSuccess) {
      testimonialSuccess.hidden = true;
      testimonialSuccess.textContent = "";
    }

    const submitButton = testimonialForm.querySelector('button[type="submit"]');
    const originalButtonText = submitButton?.textContent || "Submit Testimonial";
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = "Sending...";
    }

    let fallbackMailto = "";

    try {
      const formData = new FormData(testimonialForm);
      const params = new URLSearchParams();

      for (const [key, value] of formData.entries()) {
        if (value instanceof File) continue;
        params.append(key, value);
      }

      fallbackMailto = `mailto:hello@houseofvisualsco.com?subject=${encodeURIComponent("New House of Visuals Testimonial")}&body=${encodeURIComponent(
        [...params.entries()].map(([key, value]) => `${key}: ${value}`).join("\n")
      )}`;

      const response = await fetch("/api/testimonial", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body: params.toString(),
      });
      const result = await response.json().catch(() => ({
        ok: false,
        message: "The testimonial service is not available from this server."
      }));

      if (!response.ok || !result.ok) {
        throw new Error(result.message || "We could not send your testimonial right now.");
      }

      if (testimonialSuccess) {
        testimonialSuccess.hidden = false;
        testimonialSuccess.textContent =
          result.message || "Thank you for sharing your experience. We’ll review your testimonial before publishing.";
        testimonialSuccess.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      testimonialForm.reset();
    } catch (error) {
      if (testimonialSuccess) {
        testimonialSuccess.hidden = false;
        const cannotReachServer = error instanceof TypeError || /failed to fetch|not available from this server/i.test(error.message || "");
        testimonialSuccess.textContent = cannotReachServer
          ? "We could not reach the testimonial service from this page. Please send your testimonial directly to hello@houseofvisualsco.com."
          : error.message || "Something went wrong while sending your testimonial. Please try again.";
        if (cannotReachServer && fallbackMailto) {
          const fallbackLink = document.createElement("a");
          fallbackLink.href = fallbackMailto;
          fallbackLink.textContent = " Open email draft";
          fallbackLink.style.fontWeight = "700";
          testimonialSuccess.appendChild(fallbackLink);
        }
        testimonialSuccess.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
      }
    }
  });
}

const demoCategoryOpeners = [...document.querySelectorAll("[data-demo-open]")];
const demoExperienceModal = document.querySelector("#demoExperienceModal");
const demoExperienceClose = document.querySelector("#demoExperienceClose");
const demoIndustryTitle = document.querySelector("#demoIndustryTitle");
const demoIndustryDesc = document.querySelector("#demoIndustryDesc");

if (demoCategoryOpeners.length && demoExperienceModal) {
  const openDemoExperience = (industry = "Industry Demo", desc = "Strategic showcase placeholder.") => {
    if (demoIndustryTitle) demoIndustryTitle.textContent = industry;
    if (demoIndustryDesc) demoIndustryDesc.textContent = desc;
    demoExperienceModal.classList.add("open");
    demoExperienceModal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  };

  const closeDemoExperience = () => {
    demoExperienceModal.classList.remove("open");
    demoExperienceModal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  };

  demoCategoryOpeners.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      const isButton = event.target.closest("button") || event.target.closest("a");
      if (isButton) event.preventDefault();
      const industry = trigger.getAttribute("data-industry") || "Industry Demo";
      const desc = trigger.getAttribute("data-desc") || "Strategic showcase placeholder.";
      openDemoExperience(industry, desc);
    });

    trigger.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const industry = trigger.getAttribute("data-industry") || "Industry Demo";
        const desc = trigger.getAttribute("data-desc") || "Strategic showcase placeholder.";
        openDemoExperience(industry, desc);
      }
    });

    if (!trigger.hasAttribute("tabindex")) trigger.setAttribute("tabindex", "0");
    if (!trigger.hasAttribute("role")) trigger.setAttribute("role", "button");
  });

  demoExperienceClose?.addEventListener("click", closeDemoExperience);

  demoExperienceModal.addEventListener("click", (event) => {
    if (event.target === demoExperienceModal) closeDemoExperience();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && demoExperienceModal.classList.contains("open")) {
      closeDemoExperience();
    }
  });
}
