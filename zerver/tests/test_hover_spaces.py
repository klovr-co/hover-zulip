import orjson
from typing_extensions import override

from hover.actions_spaces import do_create_space
from hover.models import Space, SpaceAdministrator, SpaceMembership
from zerver.actions.channel_folders import check_add_channel_folder
from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.events import apply_events, fetch_initial_state_data
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import get_system_user_group_by_name
from zerver.models import ChannelFolder, Recipient, Stream, Subscription, UserProfile
from zerver.models.groups import SystemGroups


class HoverSpacesTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.creator = self.example_user("hamlet")
        self.realm = self.creator.realm
        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.MEMBERS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.category = check_add_channel_folder(
            self.realm,
            "Programs",
            "Long-running programs.",
            acting_user=self.example_user("iago"),
        )

    def create_space(self, user: UserProfile | None = None) -> Space:
        if user is None:
            user = self.creator
        return do_create_space(
            user,
            name="Launch readiness",
            description="Prepare the program before launch.",
            category=self.category,
        )

    def test_create_setup_space_is_flat_and_creates_no_native_messaging_objects(self) -> None:
        self.login_user(self.creator)
        object_counts = (
            Stream.objects.count(),
            Recipient.objects.count(),
            Subscription.objects.count(),
        )

        result = self.client_post(
            "/json/hover/spaces",
            {
                "name": "  Launch readiness  ",
                "description": "  Prepare the program before launch.  ",
                "category_id": orjson.dumps(self.category.id).decode(),
            },
        )
        self.assert_json_success(result)
        space_data = orjson.loads(result.content)["space"]
        space = Space.objects.get(id=space_data["id"])

        self.assertEqual(space.name, "Launch readiness")
        self.assertEqual(space.description, "Prepare the program before launch.")
        self.assertEqual(space.state, Space.State.SETUP)
        self.assertEqual(space.category, self.category)
        self.assertIsNone(space.stream_id)
        self.assertEqual(
            list(space.administrator_assignments.values_list("user_id", flat=True)),
            [self.creator.id],
        )
        self.assertEqual(
            object_counts,
            (
                Stream.objects.count(),
                Recipient.objects.count(),
                Subscription.objects.count(),
            ),
        )

        duplicate = self.client_post(
            "/json/hover/spaces",
            {
                "name": "launch READINESS",
                "category_id": orjson.dumps(self.category.id).decode(),
            },
        )
        self.assert_json_error(duplicate, "Space name already in use.")

    def test_disabled_and_permission_denied(self) -> None:
        self.login_user(self.creator)
        self.realm.hover_enabled = False
        self.realm.save(update_fields=["hover_enabled"])
        result = self.client_post(
            "/json/hover/spaces",
            {"name": "Private program", "category_id": orjson.dumps(self.category.id).decode()},
        )
        self.assert_json_error(result, "You do not have permission to create Spaces.")

        self.login("iago")
        result = self.client_post(
            "/json/hover/spaces",
            {"name": "Admin program", "category_id": orjson.dumps(self.category.id).decode()},
        )
        self.assert_json_error(result, "You do not have permission to create Spaces.")

        self.realm.hover_enabled = True
        self.realm.save(update_fields=["hover_enabled"])
        result = self.client_post(
            "/json/hover/spaces",
            {"name": "Admin program", "category_id": orjson.dumps(self.category.id).decode()},
        )
        self.assert_json_success(result)

    def test_realm_admin_can_grant_and_revoke_space_creation_permission(self) -> None:
        administrators = get_system_user_group_by_name(SystemGroups.ADMINISTRATORS, self.realm.id)
        members = get_system_user_group_by_name(SystemGroups.MEMBERS, self.realm.id)
        self.login("iago")

        result = self.client_patch(
            "/json/realm",
            {
                "can_create_spaces_group": orjson.dumps(
                    {"old": members.id, "new": administrators.id}
                ).decode()
            },
        )
        self.assert_json_success(result)
        self.realm.refresh_from_db()
        self.assertEqual(self.realm.can_create_spaces_group_id, administrators.id)
        self.assertFalse(self.creator.can_create_hover_spaces(self.realm))
        self.assertTrue(self.example_user("iago").can_create_hover_spaces(self.realm))

        result = self.client_patch(
            "/json/realm",
            {
                "can_create_spaces_group": orjson.dumps(
                    {"old": administrators.id, "new": members.id}
                ).decode()
            },
        )
        self.assert_json_success(result)
        self.realm.refresh_from_db()
        self.assertEqual(self.realm.can_create_spaces_group_id, members.id)
        self.assertTrue(self.creator.can_create_hover_spaces(self.realm))

        self.realm.hover_enabled = True
        self.realm.can_create_spaces_group = get_system_user_group_by_name(
            SystemGroups.ADMINISTRATORS, self.realm.id
        )
        self.realm.save(update_fields=["hover_enabled", "can_create_spaces_group"])
        self.login_user(self.creator)
        result = self.client_post(
            "/json/hover/spaces",
            {"name": "Private program", "category_id": orjson.dumps(self.category.id).decode()},
        )
        self.assert_json_error(result, "You do not have permission to create Spaces.")

    def test_setup_visibility_requires_an_explicit_space_administrator(self) -> None:
        space = self.create_space()
        realm_admin = self.example_user("iago")
        unrelated_member = self.example_user("othello")

        for user in [realm_admin, unrelated_member]:
            self.login_user(user)
            result = self.client_get("/json/hover/spaces")
            self.assert_json_success(result)
            self.assertEqual(orjson.loads(result.content)["spaces"], [])
            result = self.client_get(f"/json/hover/spaces/{space.id}")
            self.assert_json_error(result, "Invalid Space ID")

        self.login_user(realm_admin)
        SpaceMembership.objects.create(
            realm=self.realm,
            space=space,
            user=realm_admin,
            role=SpaceMembership.Role.CONTRIBUTOR,
            added_by=self.creator,
        )
        result = self.client_delete(f"/json/hover/spaces/{space.id}/admins/{self.creator.id}")
        self.assert_json_error(result, "A Space must have at least one administrator.")

        with self.capture_send_event_calls(expected_num_events=2) as events:
            result = self.client_post(
                f"/json/hover/spaces/{space.id}/admins",
                {"user_id": orjson.dumps(realm_admin.id).decode()},
            )
        self.assert_json_success(result)
        add_event = next(event for event in events if event["event"]["op"] == "add")
        self.assertEqual(add_event["users"], [realm_admin.id])
        self.assertNotIn(self.example_user("cordelia").id, add_event["users"])

        result = self.client_get(f"/json/hover/spaces/{space.id}")
        self.assert_json_success(result)
        self.assertEqual(orjson.loads(result.content)["space"]["id"], space.id)

        result = self.client_delete(f"/json/hover/spaces/{space.id}/admins/{self.creator.id}")
        self.assert_json_success(result)
        self.login_user(self.creator)
        self.assert_json_error(
            self.client_get(f"/json/hover/spaces/{space.id}"), "Invalid Space ID"
        )

        self.login_user(realm_admin)
        result = self.client_delete(f"/json/hover/spaces/{space.id}/admins/{realm_admin.id}")
        self.assert_json_error(result, "A Space must have at least one administrator.")

    def test_initial_state_and_events_converge(self) -> None:
        state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        self.assertEqual(state["hover_spaces"], [])

        with self.capture_send_event_calls(expected_num_events=1) as events:
            space = self.create_space()
        event = events[0]["event"]
        self.assertEqual(events[0]["users"], [self.creator.id])
        self.assertEqual(event["op"], "add")

        apply_events(
            self.creator,
            state=state,
            events=[event],
            fetch_event_types={"hover_space"},
            client_gravatar=False,
            slim_presence=False,
            include_subscribers=False,
            linkifier_url_template=False,
            user_list_incomplete=False,
            include_deactivated_groups=False,
        )
        fresh_state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        self.assertEqual(state["hover_spaces"], fresh_state["hover_spaces"])
        self.assertEqual(state["hover_spaces"][0]["id"], space.id)

    def test_disable_enable_cycle_retains_authorized_state_for_convergence(self) -> None:
        space = self.create_space()
        state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        self.assertEqual(state["hover_spaces"][0]["id"], space.id)

        realm_events = []
        for enabled in [False, True]:
            with self.capture_send_event_calls(expected_num_events=1) as events:
                do_set_realm_property(
                    self.realm, "hover_enabled", enabled, acting_user=self.example_user("iago")
                )
            realm_events.append(events[0]["event"])

        apply_events(
            self.creator,
            state=state,
            events=realm_events,
            fetch_event_types={"realm", "hover_space"},
            client_gravatar=False,
            slim_presence=False,
            include_subscribers=False,
            linkifier_url_template=False,
            user_list_incomplete=False,
            include_deactivated_groups=False,
        )
        fresh_state = fetch_initial_state_data(
            self.creator, realm=self.realm, event_types={"hover_space"}
        )
        self.assertTrue(state["realm_hover_enabled"])
        self.assertEqual(state["hover_spaces"], fresh_state["hover_spaces"])

    def test_cross_realm_and_archived_categories_are_rejected(self) -> None:
        self.login_user(self.creator)
        other_realm_category = ChannelFolder.objects.create(
            realm=self.lear_user("cordelia").realm,
            name="Other realm",
            description="",
            rendered_description="",
            order=1,
        )
        result = self.client_post(
            "/json/hover/spaces",
            {
                "name": "Wrong realm",
                "category_id": orjson.dumps(other_realm_category.id).decode(),
            },
        )
        self.assert_json_error(result, "Invalid Space category.")

        self.category.is_archived = True
        self.category.save(update_fields=["is_archived"])
        result = self.client_post(
            "/json/hover/spaces",
            {
                "name": "Archived category",
                "category_id": orjson.dumps(self.category.id).decode(),
            },
        )
        self.assert_json_error(result, "Invalid Space category.")

        self.assertFalse(SpaceAdministrator.objects.filter(space__name="Wrong realm").exists())
