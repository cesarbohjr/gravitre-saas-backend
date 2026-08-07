import {
  CONSENT_BANNER_REGIONS,
  MARKETING_CONSENT_STORAGE_KEY,
} from "@/lib/marketing-consent"
import { MARKETING_GTM_ID, MARKETING_GTM_NOSCRIPT_SRC } from "@/lib/marketing-gtm"

export { MARKETING_GTM_ID } from "@/lib/marketing-gtm"

/**
 * Consent Mode (Advanced) defaults + Google Tag Manager bootstrap.
 *
 * Uses blocking inline scripts (not next/script afterInteractive) so Tag Assistant
 * sees consent defaults before gtm.js — fixes "Default consent set too late" /
 * empty Consent tab from Google's consent mode troubleshooting guide.
 *
 * @see https://support.google.com/tagmanager/answer/14522438#issues
 * @see https://developers.google.com/tag-platform/security/guides/consent?consentmode=advanced
 */
export function GoogleTagManager() {
  const regionList = CONSENT_BANNER_REGIONS.map((code) => `'${code}'`).join(",")

  const consentBootstrap = `
window.dataLayer = window.dataLayer || [];
function gtag(){window.dataLayer.push(arguments);}
window.gtag = gtag;

gtag('consent', 'default', {
  ad_storage: 'denied',
  ad_user_data: 'denied',
  ad_personalization: 'denied',
  analytics_storage: 'denied',
  region: [${regionList}],
  wait_for_update: 500
});

gtag('consent', 'default', {
  ad_storage: 'granted',
  ad_user_data: 'granted',
  ad_personalization: 'granted',
  analytics_storage: 'granted'
});

gtag('set', 'ads_data_redaction', true);
gtag('set', 'url_passthrough', true);

try {
  var raw = localStorage.getItem('${MARKETING_CONSENT_STORAGE_KEY}');
  if (raw) {
    var parsed = JSON.parse(raw);
    if (parsed && parsed.ad_storage && parsed.analytics_storage) {
      gtag('consent', 'update', {
        ad_storage: parsed.ad_storage,
        ad_user_data: parsed.ad_user_data || parsed.ad_storage,
        ad_personalization: parsed.ad_personalization || parsed.ad_storage,
        analytics_storage: parsed.analytics_storage
      });
    }
  }
} catch (e) {}
`.trim()

  // Defer gtm.js until idle/load so homepage LCP/TBT aren't blocked by ~237KiB unused JS.
  // Consent defaults stay synchronous (Google: must not be set too late).
  const gtmBootstrap = `
(function(w,d,s,l,i){
  function loadGtm(){
    w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime(),event:'gtm.js'});
    var f=d.getElementsByTagName(s)[0],j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';
    j.async=true;j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;
    f.parentNode.insertBefore(j,f);
  }
  if (w.requestIdleCallback) {
    w.requestIdleCallback(loadGtm, { timeout: 3500 });
  } else {
    w.addEventListener('load', function(){ setTimeout(loadGtm, 1); });
  }
})(window,document,'script','dataLayer','${MARKETING_GTM_ID}');
`.trim()

  return (
    <>
      {/* Sync: must run before gtm.js (Google: default consent must not be set too late). */}
      <script dangerouslySetInnerHTML={{ __html: consentBootstrap }} />
      {/* Google Tag Manager (idle-deferred) */}
      <script dangerouslySetInnerHTML={{ __html: gtmBootstrap }} />
      {/* Google Tag Manager (noscript) */}
      <noscript>
        <iframe
          src={MARKETING_GTM_NOSCRIPT_SRC}
          height="0"
          width="0"
          style={{ display: "none", visibility: "hidden" }}
          title="Google Tag Manager"
        />
      </noscript>
    </>
  )
}
