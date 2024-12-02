import difflib
import logging

from tree_sitter import Language, Node, Parser, Tree

from infer import InferReport


class LanguageParser:
    __parser: Parser = None
    __language: Language = None
    __instance: "LanguageParser" = None
    __trees: dict = None

    def __new__(cls):
        if cls.__instance == None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    def __init__(self: "LanguageParser"):
        library_path = "/infer-worker/lib/c-parser.so"

        self.__language = Language(library_path, "c")

        self.__parser = Parser()
        self.__parser.set_language(self.__language)
        self.__trees = dict()

    def __cache_file(self: "LanguageParser", filepath: str):
        if self.__trees.get(filepath) == None:
            with open(filepath, "rb") as f:
                content = f.read()

            self.__trees[filepath] = {
                "tree": self.__parser.parse(content),
                "content": content.decode(),
            }

    def get_tree(self: "LanguageParser", filepath: str) -> Tree:
        self.__cache_file(filepath)

        return self.__trees[filepath]["tree"]

    def get_source(self: "LanguageParser", filepath: str) -> str:
        self.__cache_file(filepath)

        return self.__trees[filepath]["content"]

    def get_procedure(self: "LanguageParser", filepath: str, line: int) -> Node:
        tree = self.get_tree(filepath)

        query = self.__language.query("(function_definition) @functions")

        for node in map(lambda node: node[0], query.captures(tree.root_node)):
            if node.start_point[0] <= line and node.end_point[0] >= line:
                return node

        return None

    def extract_from_source(self: "LanguageParser", node: Node, filepath: str) -> str:
        if (source_file := self.get_source(filepath)) != None:
            return source_file[node.start_byte : node.end_byte]

        return None


class ContextParser:
    @staticmethod
    def update_procedures_line(reports: list[InferReport]):
        """
        This function is used to get the line number of the function where the bug was found.
        """
        language_parser = LanguageParser()

        for i, report in enumerate(reports):
            logging.debug(
                "(old) report bug @line %d, function @line %d",
                report.line,
                report.procedure_line,
            )

            traced_procedure = report.bug_trace[-1]
            reports[i].line = traced_procedure["line_number"]

            node = language_parser.get_procedure(report.source_path, report.line)

            if node is not None:
                reports[i].procedure_line = node.start_point[0]
                logging.debug(
                    "(new) report bug @line %d, function @line %d",
                    report.line,
                    report.procedure_line,
                )

    @staticmethod
    def get_prompt(procedure_vulnerabilities: list[InferReport]):
        language_parser = LanguageParser()
        procedure_line = procedure_vulnerabilities[0].procedure_line

        node = language_parser.get_procedure(
            procedure_vulnerabilities[0].source_path,
            procedure_line,
        )

        if node is not None:
            vulnerable_code = language_parser.extract_from_source(
                node, procedure_vulnerabilities[0].source_path
            )
            vulnerable_code_lines = vulnerable_code.split("\n")

            for report in procedure_vulnerabilities:
                vulnerable_code_lines.insert(
                    max(0, report.line - procedure_line - 1),
                    f"// [Unsafe] {report.bug_type}: {report.qualifier}",
                )

            prompt = "\n".join(vulnerable_code_lines)

            return prompt

        return None

    @staticmethod
    def get_patch(source_path: str, procedure_line: int, response: str):
        logging.info(
            "Creating patch for file %s, function @line %d", source_path, procedure_line
        )

        language_parser = LanguageParser()

        node = language_parser.get_procedure(
            source_path,
            procedure_line,
        )

        source = language_parser.get_source(source_path)
        patched_source = ""

        if node is not None:
            start = node.start_byte
            end = node.end_byte

            patched_source = source[:start] + response + source[end:]

            logging.info("Original file: %s\nPatched file: %s", source, patched_source)

            source_path = source_path.split("repository/")[1]
            patch = difflib.unified_diff(
                source.splitlines(keepends=True),
                patched_source.splitlines(keepends=True),
                fromfile=source_path,
                tofile=source_path,
            )

            return "".join(patch)
