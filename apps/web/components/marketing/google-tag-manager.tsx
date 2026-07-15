import Script from "next/script"

import {
  CONSENT_BANNER_REGIONS,
  MARKETING_CONSENT_STORAGE_KEY,
} from "@/lib/marketing-consent"
import { MARKETING_GTM_ID, MARKETING_GTM_NOSCRIPT_SRC } from "@/lib/marketing-gtm"

export { MARKETING_GTM_ID } from "@/lib/marketing-gtm"

/**
 * Consent Mode (Advanced) defaults + Google Tag Manager bootstrap.
 *
 * Order matches Google's GTM + custom banner guidance:
 * 1) define dataLayer / gtag
 * 2) set region-scoped consent defaults (+ restore stored choice)
 * 3) load GTM from googletagmanager.com
 *
 * @see https://developers.google.com/tag-platform/security/guides/consent?consentmode=advanced
 * @see https://developers.google.com/tag-platform/tag-manager/installation
 */
export function GoogleTagManager() {
  const regionList = CONSENT_BANNER_REGIONS.map((code) => `'${code}'`).join(",")

  return (
    <>
      <Script id="google-consent-and-gtm" strategy="afterInteractive">{`
(function(){
  window.dataLayer = window.dataLayer || [];
  function gtag(){window.dataLayer.push(arguments);}
  window.gtag = gtag;

  // Consent Mode v2 defaults for regions where the banner is shown (denied).
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied',
    region: [${regionList}],
    wait_for_update: 500
  });

  // Outside those regions: grant by default so measurement is preserved.
  gtag('consent', 'default', {
    ad_storage: 'granted',
    ad_user_data: 'granted',
    ad_personalization: 'granted',
    analytics_storage: 'granted'
  });

  // Advanced consent helpers (cookieless pings / redaction when ads denied).
  gtag('set', 'ads_data_redaction', true);
  gtag('set', 'url_passthrough', true);

  // Restore a prior choice before GTM tags evaluate consent.
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

  (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
  new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
  j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
  'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
  })(window,document,'script','dataLayer','${MARKETING_GTM_ID}');
})();
      `}</Script>
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
