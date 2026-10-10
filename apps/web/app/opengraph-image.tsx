import { OG_SIZE, socialImage } from "../lib/og";
import { PLATFORM } from "../lib/nexora/platform";

export const alt = `${PLATFORM.name}: ${PLATFORM.tagline}`;
export const size = OG_SIZE;
export const contentType = "image/png";

export default function Image() {
  return socialImage(PLATFORM.tagline, PLATFORM.headline, "onenexora.com");
}
