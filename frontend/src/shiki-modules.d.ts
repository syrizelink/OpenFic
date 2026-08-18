declare module "shiki/langs/*" {
  import type { LanguageRegistration } from "shiki/core";

  const language: LanguageRegistration;
  export default language;
}

declare module "shiki/themes/*" {
  import type { ThemeRegistrationAny } from "shiki/core";

  const theme: ThemeRegistrationAny;
  export default theme;
}
