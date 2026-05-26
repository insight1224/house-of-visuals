(function () {
  const qs = new URLSearchParams(window.location.search);
  const kitKey = (qs.get("kit") || "network").toLowerCase();

  const KITS = {
    network: {
      name: "Network & Connect",
      brand: "HOUSE OF VISUALS PRESENTS",
      title: "NETWORK & CONNECT",
      subtitle: "Build meaningful connections in a premium event setting.",
      date: "SATURDAY, JUNE 20",
      time: "7:00 PM - 10:00 PM",
      venue: "CAPITAL LOUNGE BALLROOM",
      address: "3117 CAPITAL BLVD, RALEIGH, NC",
      cta: "RESERVE YOUR SPOT",
      footer: "NETWORK. LEARN. ELEVATE.",
      accent: "#c9a24f",
      bg: "#111111",
      textColor: "#ffffff",
      font: "Cinzel, serif",
      checkout: "network-connect"
    },
    cookout: {
      name: "Community Cookout",
      brand: "COMMUNITY SPOTLIGHT SERIES",
      title: "COMMUNITY COOKOUT",
      subtitle: "Bring the neighborhood together for food, music, and connection.",
      date: "SUNDAY, JULY 14",
      time: "2:00 PM - 7:00 PM",
      venue: "LINCOLN PARK FIELD",
      address: "224 OAK STREET, CHARLOTTE, NC",
      cta: "JOIN THE CELEBRATION",
      footer: "GOOD FOOD. GOOD PEOPLE. GOOD VIBES.",
      accent: "#d58b35",
      bg: "#2a3a2f",
      textColor: "#fdf7e8",
      font: "Manrope, sans-serif",
      checkout: "community-cookout"
    },
    openmic: {
      name: "Open Mic Night",
      brand: "CITY LIGHTS ENTERTAINMENT",
      title: "OPEN MIC NIGHT",
      subtitle: "A night of live talent, spoken word, and unforgettable performances.",
      date: "FRIDAY, AUGUST 9",
      time: "8:30 PM - 12:00 AM",
      venue: "VELVET ROOM STAGE",
      address: "87 DOWNTOWN WAY, ATLANTA, GA",
      cta: "GET YOUR TICKETS",
      footer: "LIVE TALENT. LATE NIGHT ENERGY.",
      accent: "#a65bff",
      bg: "#141022",
      textColor: "#ffffff",
      font: "Cinzel, serif",
      checkout: "open-mic-night"
    }
  };

  const defaults = KITS[kitKey] || KITS.network;

  const editorTitle = document.getElementById("editorTitle");
  const flyerCanvas = document.getElementById("flyerCanvas");
  const flyerPreviewCanvas = document.getElementById("flyerPreviewCanvas");
  const flyerPreviewModal = document.getElementById("flyerPreviewModal");

  const fields = {
    brand: document.getElementById("fBrand"),
    title: document.getElementById("fTitle"),
    subtitle: document.getElementById("fSubtitle"),
    date: document.getElementById("fDate"),
    time: document.getElementById("fTime"),
    venue: document.getElementById("fVenue"),
    address: document.getElementById("fAddress"),
    cta: document.getElementById("fCta"),
    footer: document.getElementById("fFooter"),
    accent: document.getElementById("fAccent"),
    bg: document.getElementById("fBg"),
    textColor: document.getElementById("fTextColor"),
    font: document.getElementById("fFont"),
    glow: document.getElementById("fGlow"),
    shadow: document.getElementById("fShadow"),
    border: document.getElementById("fBorder"),
    bgUpload: document.getElementById("fBgUpload"),
    logoUpload: document.getElementById("fLogoUpload")
  };

  const slots = {
    brand: document.getElementById("flyerBrand"),
    title: document.getElementById("flyerTitle"),
    subtitle: document.getElementById("flyerSubtitle"),
    date: document.getElementById("flyerDate"),
    time: document.getElementById("flyerTime"),
    venue: document.getElementById("flyerVenue"),
    address: document.getElementById("flyerAddress"),
    cta: document.getElementById("flyerCta"),
    footer: document.getElementById("flyerFooter"),
    logo: document.getElementById("flyerLogo")
  };

  const resetBtn = document.getElementById("resetFlyerDemo");
  const toggleMobileBtn = document.getElementById("toggleMobilePreview");
  const previewBtn = document.getElementById("openFlyerPreview");
  const closePreviewBtn = document.getElementById("closeFlyerPreview");
  const buyBtn = document.getElementById("buyFlyerTemplate");

  let bgImageData = "";
  let logoImageData = "";

  function applyTypographyAndEffects() {
    const font = fields.font.value;
    const textColor = fields.textColor.value;
    const accent = fields.accent.value;

    Object.values(slots).forEach((el) => {
      if (!el) return;
      el.style.fontFamily = font;
      el.style.color = textColor;
      el.style.textShadow = fields.shadow.checked ? "0 8px 18px rgba(0,0,0,0.45)" : "none";
      el.style.filter = fields.glow.checked ? "drop-shadow(0 0 10px rgba(201,162,79,0.6))" : "none";
    });

    if (slots.title) slots.title.style.color = accent;
    if (slots.cta) {
      slots.cta.style.color = "#111";
      slots.cta.style.backgroundColor = accent;
      slots.cta.style.borderColor = accent;
    }

    flyerCanvas.style.color = textColor;
    flyerCanvas.style.setProperty("--flyer-accent", accent);
    flyerCanvas.style.setProperty("--flyer-text", textColor);
  }

  function applyLayoutSkin() {
    flyerCanvas.style.backgroundColor = fields.bg.value;
    flyerCanvas.style.border = fields.border.checked ? `2px solid ${fields.accent.value}` : "2px solid transparent";

    if (bgImageData) {
      flyerCanvas.style.backgroundImage = `linear-gradient(rgba(0,0,0,.48), rgba(0,0,0,.48)), url(${bgImageData})`;
      flyerCanvas.style.backgroundSize = "cover";
      flyerCanvas.style.backgroundPosition = "center";
    } else {
      flyerCanvas.style.backgroundImage = "radial-gradient(circle at 15% 15%, rgba(255,255,255,0.08), transparent 34%), linear-gradient(160deg, rgba(255,255,255,0.06), rgba(0,0,0,0.2))";
      flyerCanvas.style.backgroundSize = "auto";
      flyerCanvas.style.backgroundPosition = "center";
    }
  }

  function syncText() {
    slots.brand.textContent = fields.brand.value || "Add Brand";
    slots.title.textContent = fields.title.value || "Add Event Title";
    slots.subtitle.textContent = fields.subtitle.value || "Add Subheading";
    slots.date.textContent = fields.date.value || "Add Date";
    slots.time.textContent = fields.time.value || "Add Time";
    slots.venue.textContent = fields.venue.value || "Add Venue";
    slots.address.textContent = fields.address.value || "Add Address";
    slots.cta.textContent = fields.cta.value || "Add CTA";
    slots.footer.textContent = fields.footer.value || "Add Footer Text";
  }

  function applyAll() {
    syncText();
    applyTypographyAndEffects();
    applyLayoutSkin();
  }

  function setLogoImage(dataUrl) {
    if (!slots.logo) return;
    logoImageData = dataUrl || "";
    if (logoImageData) {
      slots.logo.innerHTML = `<img src="${logoImageData}" alt="Uploaded logo" />`;
      slots.logo.classList.add("has-image");
    } else {
      slots.logo.textContent = "Upload Logo";
      slots.logo.classList.remove("has-image");
    }
  }

  function bindInput(input, handler) {
    if (!input) return;
    input.addEventListener("input", handler);
    input.addEventListener("change", handler);
  }

  function loadImageFromInput(input, cb) {
    const file = input?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => cb(String(reader.result || ""));
    reader.readAsDataURL(file);
  }

  function resetDefaults() {
    Object.entries({
      brand: defaults.brand,
      title: defaults.title,
      subtitle: defaults.subtitle,
      date: defaults.date,
      time: defaults.time,
      venue: defaults.venue,
      address: defaults.address,
      cta: defaults.cta,
      footer: defaults.footer
    }).forEach(([key, value]) => {
      if (fields[key]) fields[key].value = value;
    });

    fields.accent.value = defaults.accent;
    fields.bg.value = defaults.bg;
    fields.textColor.value = defaults.textColor;
    fields.font.value = defaults.font;
    fields.glow.checked = false;
    fields.shadow.checked = true;
    fields.border.checked = true;
    if (fields.bgUpload) fields.bgUpload.value = "";
    if (fields.logoUpload) fields.logoUpload.value = "";

    bgImageData = "";
    setLogoImage("");
    flyerCanvas.classList.remove("is-mobile");
    toggleMobileBtn.textContent = "Mobile Preview";

    if (buyBtn) {
      buyBtn.href = `./template-checkout.html?template=${encodeURIComponent(defaults.checkout)}`;
    }

    applyAll();
  }

  function openPreview() {
    if (!flyerPreviewModal || !flyerPreviewCanvas) return;
    flyerPreviewCanvas.innerHTML = flyerCanvas.outerHTML;
    flyerPreviewModal.classList.add("open");
    flyerPreviewModal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closePreview() {
    if (!flyerPreviewModal) return;
    flyerPreviewModal.classList.remove("open");
    flyerPreviewModal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  function init() {
    if (editorTitle) editorTitle.textContent = `${defaults.name} Demo Editor`;

    [
      fields.brand,
      fields.title,
      fields.subtitle,
      fields.date,
      fields.time,
      fields.venue,
      fields.address,
      fields.cta,
      fields.footer,
      fields.accent,
      fields.bg,
      fields.textColor,
      fields.font,
      fields.glow,
      fields.shadow,
      fields.border
    ].forEach((el) => bindInput(el, applyAll));

    fields.bgUpload?.addEventListener("change", () => {
      loadImageFromInput(fields.bgUpload, (data) => {
        bgImageData = data;
        applyLayoutSkin();
      });
    });

    fields.logoUpload?.addEventListener("change", () => {
      loadImageFromInput(fields.logoUpload, (data) => {
        setLogoImage(data);
      });
    });

    toggleMobileBtn?.addEventListener("click", () => {
      flyerCanvas.classList.toggle("is-mobile");
      const mobile = flyerCanvas.classList.contains("is-mobile");
      toggleMobileBtn.textContent = mobile ? "Desktop Preview" : "Mobile Preview";
    });

    previewBtn?.addEventListener("click", openPreview);
    closePreviewBtn?.addEventListener("click", closePreview);
    flyerPreviewModal?.addEventListener("click", (event) => {
      if (event.target === flyerPreviewModal) closePreview();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && flyerPreviewModal?.classList.contains("open")) closePreview();
    });

    resetBtn?.addEventListener("click", resetDefaults);

    resetDefaults();
  }

  init();
})();
