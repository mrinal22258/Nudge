import { shield } from "../../components/icons";
import { Tooltip } from "../../components/Tooltip";
import { useI18n } from "../../i18n";

export const EncryptedIcon = () => {
  const { t } = useI18n();

  return (
    <button
      className="encrypted-icon tooltip"
      style={{
        background: "none",
        border: "none",
        padding: 0,
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
      }}
      onClick={() => {
        alert("Nudge encryption documentation is waiting to be developed!");
      }}
      aria-label={t("encrypted.link")}
    >
      <Tooltip label={t("encrypted.tooltip")} long={true}>
        {shield}
      </Tooltip>
    </button>
  );
};
