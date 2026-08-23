import { Checkbox, IconButton, Text, TextField } from "@radix-ui/themes";
import axios from "axios";
import { LockOpen } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";

import { loginWithPassword } from "@/lib/api-client";

import "./auth-page.css";

export function AuthPage() {
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [trustDevice, setTrustDevice] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasLoginError, setHasLoginError] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorMessage(null);
    setHasLoginError(false);
    setIsSubmitting(true);

    try {
      await loginWithPassword({ password, trust_device: trustDevice });
      window.location.reload();
    } catch (error) {
      setHasLoginError(true);
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        setErrorMessage(t("auth.invalidPassword"));
      } else {
        setErrorMessage(t("auth.loginFailed"));
      }
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <span
          className="auth-brand"
          role="img"
          aria-label={t("common.appName")}
        />
        <form
          className="auth-form"
          onSubmit={handleSubmit}
        >
          <div className="auth-entry">
            <div
              className="auth-password-frame"
              data-error={hasLoginError ? "true" : undefined}
            >
              <TextField.Root
                className="auth-password"
                type="password"
                size="2"
                placeholder={t("auth.passwordPlaceholder")}
                aria-label={t("auth.passwordPlaceholder")}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                onFocus={() => {
                  setHasLoginError(false);
                  setErrorMessage(null);
                }}
                autoFocus
                required
              />
            </div>
            <IconButton
              type="submit"
              size="2"
              aria-label={t("auth.submit")}
              title={isSubmitting ? t("auth.submitting") : t("auth.submit")}
              disabled={isSubmitting}
            >
              <LockOpen size={17} />
            </IconButton>
          </div>
          <label className="auth-trust-device">
            <Checkbox
              checked={trustDevice}
              onCheckedChange={(checked) => setTrustDevice(checked === true)}
            />
            <Text size="2">{t("auth.trustDevice")}</Text>
          </label>
          <Text
            className="auth-error"
            data-visible={errorMessage ? "true" : undefined}
            size="2"
            role={errorMessage ? "alert" : undefined}
          >
            {errorMessage ?? "\u00a0"}
          </Text>
        </form>
      </section>
    </main>
  );
}
