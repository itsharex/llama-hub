"""LLama Kibela Reader"""
from typing import Dict, List, Optional, TypeVar, Generic
from llama_index.readers.base import BaseReader
from llama_index.readers.schema.base import Document
from pydantic import BaseModel, parse_obj_as
from pydantic.generics import GenericModel


NodeType = TypeVar("NodeType")


class Edge(GenericModel, Generic[NodeType]):
    node: Optional[NodeType]
    cursor: Optional[str]


class PageInfo(BaseModel):
    startCursor: Optional[str]
    endCursor: Optional[str]
    hasNextPage: Optional[bool]


class Connection(GenericModel, Generic[NodeType]):
    nodes: Optional[List[NodeType]]
    edges: Optional[List[Edge[NodeType]]]
    pageInfo: Optional[PageInfo]
    totalCount: Optional[int]


class Note(BaseModel):
    content: Optional[str]
    id: Optional[str]
    title: Optional[str]
    url: Optional[str]


class KibelaReader(BaseReader):
    """Kibela reader.

    Reads pages from Kibela.

    Args:
        team (str): Kibela team.
        token (str): Kibela API token.
    """

    def __init__(self, team: str, token: str) -> None:
        """Initialize with parameters."""
        from gql.transport.aiohttp import AIOHTTPTransport
        from gql import Client

        self.url = f"https://{team}.kibe.la/api/v1"
        self.headers = {"Authorization": f"Bearer {token}"}
        transport = AIOHTTPTransport(url=self.url, headers=self.headers)
        self.client = Client(transport=transport,
                             fetch_schema_from_transport=True)

    def request(self, query: str, params: dict) -> Dict:
        from gql import gql

        q = gql(query)
        return self.client.execute(q, variable_values=params)

    def load_data(self) -> List[Document]:
        """Load data from Kibela.

        Returns:
            List[Document]: List of documents.

        """
        query = """
        query getNotes($after: String) {
          notes(first: 100, after: $after) {
            totalCount
            pageInfo {
              endCursor
              startCursor
              hasNextPage
            }
            edges {
              cursor
              node {
                id
                url
                title
                content
              }
            }
          }
        }
        """
        after = ""
        params = {"after": after}
        has_next = True
        documents = []
        # Due to the request limit of 10 requests per second on the Kibela API, we do not process in parallel.
        # See https://github.com/kibela/kibela-api-v1-document#1%E7%A7%92%E3%81%82%E3%81%9F%E3%82%8A%E3%81%AE%E3%83%AA%E3%82%AF%E3%82%A8%E3%82%B9%E3%83%88%E6%95%B0
        while has_next:
            res = self.request(query, params)
            note_conn = parse_obj_as(Connection[Note], res["notes"])
            for note in note_conn.edges:
                doc = f"---\nurl: {note.node.url}\ntitle: {note.node.title}\n---\ncontent:\n{note.node.content}\n"
                documents.append(Document(doc))
            has_next = note_conn.pageInfo.hasNextPage
            after = note_conn.pageInfo.endCursor

        return documents
