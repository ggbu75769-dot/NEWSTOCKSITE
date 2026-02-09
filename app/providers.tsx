"use client";

import { I18nextProvider } from "react-i18next";
import i18n from "./i18n/client";

type ProvidersProps = {
  children: React.ReactNode;
};

export default function Providers({ children }: ProvidersProps) {
  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>;
}
