UV ?= uv
GATEWAY_DIR := course_code/week01/1-7/llm-gateway
COMMERCE_DIR := course_code/week03/3-5/commerce-agents
COMMERCE_VENV ?= $(abspath $(COMMERCE_DIR)/.venv)
AGENT_PROJECTS := \
	course_code/week03/3-1/codebase_agent_demo \
	course_code/week03/3-1/codebasedemo \
	course_code/week03/3-2/codebase_agent_demo \
	course_code/week03/3-2/planning_agent_demo \
	course_code/week03/3-3/planning_agent_demo \
	course_code/week03/3-5/harness_agent

.PHONY: help install-agents install-commerce check check-gateway check-tools check-agents check-commerce check-reference check-live check-docs

help:
	@printf '%s\n' 'make install-agents  安装六个 Agent 示例的锁定依赖' \
	  'make install-commerce 安装 Commerce Python 示例的锁定依赖' \
	  'make check           运行所有已接入的离线检查' \
	  'make check-gateway   Gateway 测试与 Ruff 检查' \
	  'make check-tools     第二周的离线工具治理测试' \
	  'make check-agents    六个 Agent 示例的测试与 TypeScript 编译' \
	  'make check-commerce  Commerce 后端测试、Ruff 与一致性检查' \
	  'make check-docs      本地文档链接与章节锚点检查' \
	  'make check-reference 完整 Structured Output 示例测试和静态检查' \
	  'make check-live      DeepSeek 官网小额联调（需要根 .env，会产生费用）'

install-agents:
	@set -e; for project in $(AGENT_PROJECTS); do npm --prefix "$$project" ci --no-fund --no-audit; done

install-commerce:
	cd $(COMMERCE_DIR) && $(UV) venv --allow-existing "$(COMMERCE_VENV)"
	cd $(COMMERCE_DIR) && $(UV) pip install --python "$(COMMERCE_VENV)/bin/python" -r requirements-dev.txt

check: check-gateway check-tools check-agents check-commerce check-reference check-docs

check-gateway:
	$(UV) run --directory $(GATEWAY_DIR) --locked --extra dev python -m pytest -q
	$(UV) run --directory $(GATEWAY_DIR) --locked --extra dev ruff check .

check-tools:
	cd course_code/week02/2-2 && $(UV) run --no-project --with-requirements requirements.txt python -m pytest -q
	cd course_code/week02/2-4 && $(UV) run --no-project --with-requirements requirements.txt python -m pytest -q

check-agents:
	@set -e; for project in $(AGENT_PROJECTS); do \
	  npm --prefix "$$project" test; \
	  npm --prefix "$$project" run build; \
	done

check-commerce:
	cd $(COMMERCE_DIR) && "$(COMMERCE_VENV)/bin/python" -m pytest -q
	cd $(COMMERCE_DIR) && "$(COMMERCE_VENV)/bin/ruff" check .
	cd $(COMMERCE_DIR) && "$(COMMERCE_VENV)/bin/python" scripts/check.py

check-reference:
	$(UV) run --project $(GATEWAY_DIR) --locked --extra dev python -m pytest -q course_code/week01/1-5/test_deepseek_structured_demo.py
	$(UV) run --project $(GATEWAY_DIR) --locked --extra dev ruff check scripts/verify_deepseek.py scripts/check_docs.py course_code/week01/1-5/deepseek_structured_demo.py course_code/week01/1-5/test_deepseek_structured_demo.py

check-live:
	$(UV) run --env-file .env --project $(GATEWAY_DIR) --locked --extra dev python scripts/verify_deepseek.py

check-docs:
	$(UV) run --project $(GATEWAY_DIR) --locked --extra dev python scripts/check_docs.py
