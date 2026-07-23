# QQ Group Notifications

The `QQ group notifications` workflow sends Issue and pull-request state
changes to a QQ group through the official QQ Bot API. It runs entirely in
GitHub Actions; no continuously running relay service is required.

## Required QQ setup

1. Publish or enable the bot in the QQ Open Platform and add it to the target
   group.
2. Enable active group messages for the bot. Group members can disable active
   messages in QQ, which causes the API to reject those messages.
3. Obtain the target `group_openid` from a group event such as
   `GROUP_AT_MESSAGE_CREATE`. A QQ group number is not a `group_openid` and
   cannot be substituted for it.

The official API currently obtains a two-hour access token from
`https://bots.qq.com/app/getAppAccessToken` and sends the message to
`POST https://api.bot.qq.com/v2/groups/{group_openid}/messages`.

## Repository configuration

Create these Actions secrets under **Settings > Secrets and variables >
Actions**:

| Secret | Value |
| --- | --- |
| `QQ_BOT_APP_ID` | Bot AppID from the QQ Open Platform |
| `QQ_BOT_CLIENT_SECRET` | Bot ClientSecret from the QQ Open Platform |
| `QQ_GROUP_OPENID` | OpenID of the destination QQ group |

Do not put these values in a workflow file, Issue, pull request, Actions log, or
repository variable. The workflow requests a short-lived access token for each
run and does not print credentials or tokens.

The optional Actions variable `QQ_NOTIFICATION_INCLUDE_URL` defaults to
`true`. When QQ rejects a GitHub link with error `40054010`, the notifier
automatically retries the same message without the URL. Set the variable to
`false` to omit URLs on the first attempt.

## Verification

1. Open **Actions > QQ group notifications > Run workflow**.
2. Keep `dry_run` enabled for the first run. The run should finish without
   reading or validating the three secrets.
3. Run it again with `dry_run` disabled. Confirm that the target group receives
   the test message and that the workflow log reports a message ID.
4. Open and close a test Issue, then open and close a test pull request. Confirm
   that the action, number, title, actor, and merged/closed distinction are
   correct.

The workflow covers Issue lifecycle, assignment, label, milestone, pin, and
lock changes. It covers pull-request lifecycle, new commits, draft/review
state, assignment, labels, milestones, merge queue, and auto-merge changes.

## Security and operations

`pull_request_target` is required so notifications also work for pull requests
from forks, where normal pull-request workflows cannot read repository
secrets. The workflow checks out only `script/github/notify_qq.py` from the
trusted default branch and never checks out or executes pull-request code.

Only the item title and event metadata are sent to QQ. Issue and pull-request
bodies, comments, source code, and secret values are never included. Titles are
cleaned and bounded before transmission.

Common failures:

| QQ code | Meaning | Action |
| --- | --- | --- |
| `40034100` | Active-message rate limit exceeded | Wait for quota recovery and reduce event volume if needed |
| `40034101` / `40054003` | Bot is not in the group | Add the published bot to the target group |
| `40034105` | Active messages are not permitted | Enable the bot and group active-message permission |
| `40054010` | URL is not allowed | Automatic URL-free retry runs; optionally set `QQ_NOTIFICATION_INCLUDE_URL=false` |
| `40054016` | Bot is offline | Check bot publication and online status in the QQ Open Platform |

To stop notifications immediately, disable the workflow in GitHub Actions. To
rotate credentials, replace `QQ_BOT_CLIENT_SECRET`; no code change is needed.
