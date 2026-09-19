export const PARITY_AS_OF = "2026-09-19";
export const GOLDEN_PROJECT_ID = "proj_01H9N49B01081040G2081040G2";
export const GOLDEN_DOCUMENT_ID = "doc_01H9N49B020C1G60R30C1G60R3";
export const GOLDEN_REVISION_ID = "rev_01H9N49B030G2081040G208104";
export const MIN_TOUCH_TARGET_PT = 44;
export const DEEP_LINK = `moviemuse://project/${GOLDEN_PROJECT_ID}/revision/${GOLDEN_REVISION_ID}?platform=web`;

export const PARITY_ROWS = [
  { platform: "web", focus: "professional_authoring", longForm: true },
  { platform: "macos", focus: "professional_authoring", longForm: true },
  { platform: "windows", focus: "professional_authoring", longForm: true },
  { platform: "ios", focus: "onset_capture", longForm: false },
  { platform: "android", focus: "onset_capture", longForm: false }
] as const;

export const WEB_LIMITATIONS =
  "On-set capture and large-target Room boards are available but are not the primary job for Web, macOS, or Windows.";
