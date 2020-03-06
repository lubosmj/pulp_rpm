# coding=utf-8
"""Tests that publish rpm plugin repositories."""
import unittest
from random import choice
from xml.etree import ElementTree
from urllib.parse import urljoin

from requests.exceptions import HTTPError

from pulp_smash import api, cli, config
from pulp_smash.pulp3.utils import (
    download_content_unit,
    gen_distribution,
    gen_repo,
    get_content,
    get_content_summary,
    get_versions,
    sync,
)

from pulp_rpm.tests.functional.utils import (
    gen_rpm_remote,
)
from pulp_rpm.tests.functional.constants import (
    RPM_ALT_LAYOUT_FIXTURE_URL,
    RPM_DISTRIBUTION_PATH,
    RPM_FIXTURE_SUMMARY,
    RPM_LONG_UPDATEINFO_FIXTURE_URL,
    RPM_NAMESPACES,
    RPM_PACKAGE_CONTENT_NAME,
    RPM_PUBLICATION_PATH,
    RPM_REFERENCES_UPDATEINFO_URL,
    RPM_REMOTE_PATH,
    RPM_REPO_PATH,
    RPM_RICH_WEAK_FIXTURE_URL,
    RPM_SHA512_FIXTURE_URL,
    SRPM_UNSIGNED_FIXTURE_URL,
)
from pulp_rpm.tests.functional.utils import publish, set_up_module as setUpModule  # noqa:F401


class PublishAnyRepoVersionTestCase(unittest.TestCase):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/pulp/pulp-smash/issues/897>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest
           ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        body = gen_rpm_remote()
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        sync(self.cfg, remote, repo)

        # Step 1
        repo = self.client.get(repo['pulp_href'])
        for rpm_content in get_content(repo)[RPM_PACKAGE_CONTENT_NAME]:
            self.client.post(
                urljoin(repo['pulp_href'], 'modify/'),
                {'remove_content_units': [rpm_content['pulp_href']]}
            )
        version_hrefs = tuple(ver['pulp_href'] for ver in get_versions(repo))
        non_latest = choice(version_hrefs[:-1])

        # Step 2
        publication = publish(self.cfg, repo)

        # Step 3
        self.assertEqual(publication['repository_version'], version_hrefs[-1])

        # Step 4
        publication = publish(self.cfg, repo, non_latest)

        # Step 5
        self.assertEqual(publication['repository_version'], non_latest)

        # Step 6
        with self.assertRaises(HTTPError):
            body = {
                'repository': repo['pulp_href'],
                'repository_version': non_latest
            }
            self.client.post(RPM_PUBLICATION_PATH, body)


class SyncPublishReferencesUpdateTestCase(unittest.TestCase):
    """Sync/publish a repo that ``updateinfo.xml`` contains references."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """Sync/publish a repo that ``updateinfo.xml`` contains references.

        This test targets the following issue:

        `Pulp #3998 <https://pulp.plan.io/issues/3998>`_.
        """
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        body = gen_rpm_remote(url=RPM_REFERENCES_UPDATEINFO_URL)
        remote = self.client.post(RPM_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertIsNotNone(repo['latest_version_href'])

        content_summary = get_content_summary(repo)
        self.assertDictEqual(
            content_summary,
            RPM_FIXTURE_SUMMARY,
            content_summary
        )

        publication = publish(self.cfg, repo)
        self.addCleanup(self.client.delete, publication['pulp_href'])


class SyncPublishTestCase(unittest.TestCase):
    """Test sync and publish for different RPM repositories.

    This test targets the following issue:

    `Pulp #4108 <https://pulp.plan.io/issues/4108>`_.
    `Pulp #4134 <https://pulp.plan.io/issues/4134>`_.
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)

    def test_rpm_rich_weak(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_RICH_WEAK_FIXTURE_URL)

    def test_rpm_long_updateinfo(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_LONG_UPDATEINFO_FIXTURE_URL)

    def test_rpm_alt_layout(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_ALT_LAYOUT_FIXTURE_URL)

    def test_rpm_sha512(self):
        """Sync and publish an RPM repository. See :meth: `do_test`."""
        self.do_test(RPM_SHA512_FIXTURE_URL)

    def test_srpm(self):
        """Sync and publish a SRPM repository. See :meth: `do_test`."""
        self.do_test(SRPM_UNSIGNED_FIXTURE_URL)

    def do_test(self, url):
        """Sync and publish an RPM repository given a feed URL."""
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(RPM_REMOTE_PATH, gen_rpm_remote(url=url))
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertIsNotNone(repo['latest_version_href'])

        publication = publish(self.cfg, repo)
        self.addCleanup(self.client.delete, publication['pulp_href'])


class ValidateNoChecksumTagTestCase(unittest.TestCase):
    """Publish repository and validate the updateinfo.

    This Test does the following:

    1. Create a rpm repo and a remote.
    2. Sync the repo with the remote.
    3. Publish and distribute the repo.
    4. Check whether CheckSum tag ``sum`` not present in ``updateinfo.xml``.

    This test targets the following issue:

    * `Pulp #4109 <https://pulp.plan.io/issues/4109>`_
    * `Pulp #4033 <https://pulp.plan.io/issues/4033>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)
        raise unittest.SkipTest('Skipping until we resolve https://pulp.plan.io/issues/5507')

    def test_all(self):
        """Sync and publish an RPM repository and verify the checksum."""
        # Step 1
        repo = self.client.post(RPM_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(RPM_REMOTE_PATH, gen_rpm_remote())
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Step 2
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertIsNotNone(repo['latest_version_href'])

        # Step 3
        publication = publish(self.cfg, repo)
        self.addCleanup(self.client.delete, publication['pulp_href'])
        body = gen_distribution()
        body['publication'] = publication['pulp_href']
        distribution = self.client.using_handler(api.task_handler).post(
            RPM_DISTRIBUTION_PATH, body
        )
        self.addCleanup(self.client.delete, distribution['pulp_href'])
        # Step 4
        repo_md = ElementTree.fromstring(
            download_content_unit(self.cfg, distribution, 'repodata/repomd.xml')
        )
        update_info_content = ElementTree.fromstring(
            download_content_unit(
                self.cfg,
                distribution,
                self._get_updateinfo_xml_path(repo_md)
            )
        )
        tags = {elem.tag for elem in update_info_content.iter()}
        self.assertNotIn('sum', tags, update_info_content)

    @staticmethod
    def _get_updateinfo_xml_path(root_elem):
        """Return the path to ``updateinfo.xml.gz``, relative to repository root.

        Given a repomd.xml, this method parses the xml and returns the
        location of updateinfo.xml.gz.
        """
        # <ns0:repomd xmlns:ns0="http://linux.duke.edu/metadata/repo">
        #     <ns0:data type="primary">
        #         <ns0:checksum type="sha256">[…]</ns0:checksum>
        #         <ns0:location href="repodata/[…]-primary.xml.gz" />
        #         …
        #     </ns0:data>
        #     …
        xpath = '{{{}}}data'.format(RPM_NAMESPACES['metadata/repo'])
        data_elems = [
            elem for elem in root_elem.findall(xpath)
            if elem.get('type') == 'updateinfo'
        ]
        xpath = '{{{}}}location'.format(RPM_NAMESPACES['metadata/repo'])
        return data_elems[0].find(xpath).get('href')


class PublishSignedRepomdTestCase(unittest.TestCase):
    """A test case that verifies the publishing of repository metadata."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.cli_client = cli.Client(cls.cfg)
        cls.pkg_mgr = cli.PackageManager(cls.cfg)
        cls.api_client = api.Client(cls.cfg, api.json_handler)

    def test_publish_signed_repo_metadata(self):
        """Test if a package manager is able to install packages from a signed repository."""
        distribution = self.create_distribution()
        self.init_repository_config(distribution)
        self.install_package()

    def create_distribution(self):
        """Create a distribution with a repository that contains a signing service."""
        metadata_signing_service = self.api_client.using_handler(api.page_handler).get(
            'pulp/api/v3/signing-services/'
        )[0]

        repo = self.api_client.post(RPM_REPO_PATH, gen_repo(
            metadata_signing_service=metadata_signing_service['pulp_href']
        ))
        self.addCleanup(self.api_client.delete, repo['pulp_href'])

        remote = self.api_client.post(RPM_REMOTE_PATH, gen_rpm_remote(url=RPM_ALT_LAYOUT_FIXTURE_URL))
        self.addCleanup(self.api_client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.api_client.get(repo['pulp_href'])

        self.assertIsNotNone(repo['latest_version_href'])

        publication = publish(self.cfg, repo)
        self.addCleanup(self.api_client.delete, publication['pulp_href'])

        body = gen_distribution()
        body['publication'] = publication['pulp_href']
        distribution = self.api_client.using_handler(api.task_handler).post(
            RPM_DISTRIBUTION_PATH, body
        )
        self.addCleanup(self.api_client.delete, distribution['pulp_href'])

        return distribution

    def init_repository_config(self, distribution):
        """
        Create and initialize the repository's configuration.

        This configuration is going to be used by a package manager (dnf) afterwards.
        """
        self.cli_client.run(('sudo', 'dnf', 'config-manager', '--add-repo', distribution['base_url']))
        repo_id = '*{}'.format(distribution['base_path'])
        public_key_url = f"{distribution['base_url']}/repodata/public.key"
        self.cli_client.run(
            ('sudo', 'dnf', 'config-manager', '--save', f'--setopt={repo_id}.gpgcheck=0',
             f'--setopt={repo_id}.repo_gpgcheck=1', f'--setopt={repo_id}.gpgkey={public_key_url}',
             repo_id)
        )
        self.addCleanup(self.cli_client.run, ('sudo', 'dnf', 'config-manager', '--disable', repo_id))

    def install_package(self):
        """Install and verify the installed package."""
        rpm_name = 'walrus'
        self.pkg_mgr.install(rpm_name)
        self.addCleanup(self.pkg_mgr.uninstall, rpm_name)
        rpm = self.cli_client.run(('rpm', '-q', rpm_name)).stdout.strip().split('-')
        self.assertEqual(rpm_name, rpm[0])
