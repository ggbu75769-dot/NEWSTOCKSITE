"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";

export type UserBadgeProps = {
  name?: string | null;
  email?: string | null;
  avatarUrl?: string | null;
};

export default function UserBadge({ name, email, avatarUrl }: UserBadgeProps) {
  const [avatar, setAvatar] = useState(avatarUrl ?? "");
  const { t } = useTranslation();

  const displayName = name || email || t("user.fallback");
  const initials = displayName
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex items-center gap-3">
      {avatar ? (
        <img
          src={avatar}
          alt={displayName}
          className="h-9 w-9 rounded-full border border-border object-cover"
          referrerPolicy="no-referrer"
          onError={() => setAvatar("")}
        />
      ) : (
        <div className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card text-xs font-semibold text-foreground">
          {initials}
        </div>
      )}
      <div className="text-left">
        <p className="text-sm font-semibold text-foreground">{displayName}</p>
        {email && <p className="text-xs text-muted-foreground">{email}</p>}
      </div>
    </div>
  );
}
