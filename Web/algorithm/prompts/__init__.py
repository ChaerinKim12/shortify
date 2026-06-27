"""
===============================================================
prompts 패키지 (prompts/__init__.py)
===============================================================
카테고리 코드값("empathy" 등)으로 그 카테고리의 선정 기준 텍스트를
한 곳에서 꺼낼 수 있게 묶어둡니다.

recommend.py 는 categories=["empathy","laughter"] 같은 리스트를 받으면,
각 코드에 대해 get_category_prompt(code) 로 기준 텍스트를 가져옵니다.
즉 카테고리가 늘거나 바뀌어도 recommend.py 는 손댈 필요가 없고,
이 파일의 매핑만 고치면 됩니다.

[base.py 는 왜 여기서 안 묶나]
  base.py 는 "카테고리 기준"이 아니라 "공통 뼈대(조립 함수)"라서
  recommend.py 가 직접 import 합니다. 여기서는 카테고리 4개만 묶습니다.
===============================================================
"""

from . import empathy, laughter, info, touching


# 카테고리 코드값 -> 기준 텍스트를 반환하는 함수
# (함수를 바로 호출하지 않고 함수 자체를 담아둠. 필요할 때 호출)
_PROMPT_GETTERS = {
    "empathy": empathy.get_empathy_prompt,
    "laughter": laughter.get_laughter_prompt,
    "info": info.get_info_prompt,
    "touching": touching.get_touching_prompt,
}


def get_category_prompt(category_code: str) -> str:
    """
    카테고리 코드값으로 그 카테고리의 선정 기준 텍스트를 반환한다.

    Args:
        category_code: "empathy" / "laughter" / "info" / "touching"

    Returns:
        해당 카테고리의 선정 기준 본문 문자열

    Raises:
        KeyError: 등록되지 않은 카테고리 코드일 때
    """
    if category_code not in _PROMPT_GETTERS:
        raise KeyError(
            f"등록되지 않은 카테고리: '{category_code}' "
            f"(가능: {list(_PROMPT_GETTERS.keys())})"
        )
    # 저장해둔 함수를 이때 호출해서 텍스트를 얻는다
    return _PROMPT_GETTERS[category_code]()


def available_categories() -> list:
    """등록된 카테고리 코드 목록을 반환한다."""
    return list(_PROMPT_GETTERS.keys())