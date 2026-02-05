import json
from typing import Dict, Any, List
import re


class DataMaskingService:
    """数据脱敏服务"""

    def mask_data(self, data: Dict[str, Any], output_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """对数据进行脱敏处理"""
        if output_config is None:
            output_config = {}

        masking_rules = output_config.get("masking_rules", {})
        result = data.copy()

        if "result" in result:
            if isinstance(result["result"], dict):
                result["result"] = self._mask_dict(result["result"], masking_rules)
            elif isinstance(result["result"], list):
                result["result"] = self._mask_list(result["result"], masking_rules)

        return result

    def _mask_dict(self, data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """对字典进行脱敏"""
        masked = {}
        for key, value in data.items():
            if key in rules:
                rule = rules[key]
                masked[key] = self._apply_rule(value, rule)
            elif isinstance(value, dict):
                masked[key] = self._mask_dict(value, rules)
            elif isinstance(value, list):
                masked[key] = self._mask_list(value, rules)
            else:
                masked[key] = value
        return masked

    def _mask_list(self, data: List[Any], rules: Dict[str, Any]) -> List[Any]:
        """对列表进行脱敏"""
        masked = []
        for item in data:
            if isinstance(item, dict):
                masked.append(self._mask_dict(item, rules))
            elif isinstance(item, list):
                masked.append(self._mask_list(item, rules))
            else:
                masked.append(item)
        return masked

    def _apply_rule(self, value: Any, rule: str) -> Any:
        """应用脱敏规则"""
        if rule == "mask_all":
            # 完全掩码
            if isinstance(value, str):
                return "***"
            return None
        elif rule == "mask_partial":
            # 部分掩码（保留前后几位）
            if isinstance(value, str):
                if len(value) <= 4:
                    return "****"
                return value[:2] + "****" + value[-2:]
            return value
        elif rule == "generalize":
            # 泛化处理
            if isinstance(value, (int, float)):
                # 数值泛化到范围
                if isinstance(value, int):
                    base = (value // 10) * 10
                    return f"{base}-{base+9}"
                else:
                    base = int(value // 10) * 10
                    return f"{base}-{base+9}"
            return value
        elif rule == "hash":
            # 哈希处理
            import hashlib
            if isinstance(value, str):
                return hashlib.sha256(value.encode()).hexdigest()[:16]
            return value
        else:
            return value
